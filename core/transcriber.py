"""
Whisper 逐字稿提取模块
基于 faster-whisper + ffmpeg 进行语音转文字
支持 AI 纠错优化
"""
import os
import json
import subprocess
import httpx
from pathlib import Path
from typing import Optional, Callable

from .config import AppConfig
from .database import Database


class TranscriptExtractor:
    """语音识别引擎"""

    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db
        self.model = None

    def _load_model(self):
        """懒加载 Whisper 模型"""
        if self.model is not None:
            return

        # 优先使用 DyD 项目已缓存的模型
        dyd_models = os.path.join(self.config.dyd_path, "data", "models", "whisper")
        local_models = str(self.config.data_path / "models" / "whisper")

        # 选择存在的模型目录
        models_dir = local_models
        if os.path.exists(dyd_models) and os.listdir(dyd_models):
            models_dir = dyd_models
            print(f"[INFO] 使用 DyD 缓存模型: {models_dir}")

        os.makedirs(models_dir, exist_ok=True)
        os.environ['HF_HOME'] = models_dir
        if 'HF_ENDPOINT' not in os.environ:
            os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

        from faster_whisper import WhisperModel
        self.model = WhisperModel(
            self.config.whisper.model_size,
            device=self.config.whisper.device,
            compute_type=self.config.whisper.compute_type,
            download_root=models_dir
        )

    def extract_audio(self, video_path: str, audio_path: str) -> bool:
        """用 ffmpeg 从视频中提取音频（16kHz WAV）"""
        try:
            subprocess.run([
                'ffmpeg', '-i', video_path,
                '-ar', '16000', '-ac', '1', '-f', 'wav',
                '-y', audio_path
            ], capture_output=True, check=True, timeout=120)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def transcribe(self, aweme_id: str, progress_callback: Callable = None) -> Optional[dict]:
        """
        转写单个视频的音频
        返回: {"text": str, "srt": str, "word_count": int, "duration": float}
        """
        # 检查数据库中是否已有逐字稿
        existing = self.db.get_transcript(aweme_id)
        if existing and existing.get('transcript_text'):
            if progress_callback:
                progress_callback(f"逐字稿已存在，跳过: {aweme_id}")
            return {
                "text": existing['transcript_text'],
                "srt": existing['srt_text'],
                "word_count": existing['word_count'],
                "duration": existing['duration_seconds'],
            }

        # 查找视频文件
        video_path = self.config.downloads_path / f"{aweme_id}.mp4"
        if not video_path.exists():
            if progress_callback:
                progress_callback(f"视频文件不存在: {aweme_id}")
            return None

        # 加载模型
        if progress_callback:
            progress_callback("加载 Whisper 模型...")
        self._load_model()

        # 提取音频
        if progress_callback:
            progress_callback("提取音频...")
        audio_path = str(self.config.transcripts_path / f"{aweme_id}_audio.wav")
        if not self.extract_audio(str(video_path), audio_path):
            if progress_callback:
                progress_callback(f"音频提取失败: {aweme_id}")
            return None

        # 转写
        if progress_callback:
            progress_callback("转写中...")

        segments_iter, info = self.model.transcribe(
            audio_path,
            language=self.config.whisper.language,
            beam_size=5,
            vad_filter=True,
        )

        # 收集结果
        segments = []
        full_text_parts = []
        srt_lines = []
        idx = 1

        for seg in segments_iter:
            segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())

            # 生成 SRT 格式
            start_h, start_m, start_s = self._format_time(seg.start)
            end_h, end_m, end_s = self._format_time(seg.end)
            srt_lines.append(f"{idx}")
            srt_lines.append(f"{start_h}:{start_m}:{start_s} --> {end_h}:{end_m}:{end_s}")
            srt_lines.append(seg.text.strip())
            srt_lines.append("")
            idx += 1

        full_text = "\n".join(full_text_parts)
        srt_text = "\n".join(srt_lines)
        duration = info.duration if info else 0

        # 保存文件
        transcripts_dir = str(self.config.transcripts_path)
        os.makedirs(transcripts_dir, exist_ok=True)

        txt_path = os.path.join(transcripts_dir, f"{aweme_id}.txt")
        srt_path = os.path.join(transcripts_dir, f"{aweme_id}.srt")

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_text)

        # 清理临时音频文件
        try:
            os.remove(audio_path)
        except Exception:
            pass

        # 保存到数据库
        self.db.save_transcript(
            aweme_id=aweme_id,
            transcript_text=full_text,
            srt_text=srt_text,
            word_count=len(full_text),
            duration_seconds=duration,
        )

        if progress_callback:
            progress_callback(f"转写完成: {len(full_text)}字, {duration:.1f}秒")

        return {
            "text": full_text,
            "srt": srt_text,
            "word_count": len(full_text),
            "duration": duration,
            "txt_path": txt_path,
            "srt_path": srt_path,
        }

    def batch_transcribe(self, progress_callback: Callable = None) -> dict:
        """
        批量转写所有已下载但未转写的视频
        """
        stats = {"total": 0, "success": 0, "skipped": 0, "failed": 0}

        # 获取所有已下载的视频
        videos = self.db.get_all_videos()
        downloaded = [v for v in videos if v.get('downloaded')]

        stats["total"] = len(downloaded)

        for i, video in enumerate(downloaded):
            aweme_id = video['aweme_id']

            # 检查是否已转写
            if self.db.video_transcribed(aweme_id):
                stats["skipped"] += 1
                continue

            if progress_callback:
                progress_callback(f"[{i+1}/{len(downloaded)}] 转写: {video.get('title', '')[:30]}...")

            result = self.transcribe(aweme_id, progress_callback)
            if result:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        return stats

    @staticmethod
    def _format_time(seconds: float) -> tuple:
        """格式化时间为 SRT 格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return (
            f"{hours:02d}",
            f"{minutes:02d}",
            f"{secs:02d},{millis:03d}"
        )

    def fix_typos(self, text: str, video_title: str = "") -> str:
        """使用 LLM 纠正逐字稿中的错别字和识别错误"""
        if not self.config.llm.api_key or self.config.llm.api_key == "your-api-key":
            return text

        # 逐字稿太长时分段处理
        if len(text) > 3000:
            chunks = [text[i:i+3000] for i in range(0, len(text), 3000)]
            fixed_chunks = []
            for chunk in chunks:
                fixed = self._fix_chunk(chunk, video_title)
                fixed_chunks.append(fixed)
            return "\n".join(fixed_chunks)
        else:
            return self._fix_chunk(text, video_title)

    def _fix_chunk(self, text: str, video_title: str = "") -> str:
        """纠正单段文本的错别字"""
        system_prompt = """你是一位专业的中文校对编辑。请纠正以下语音转文字结果中的错别字、同音字错误、断句错误。

规则：
1. 只纠正明显的错别字和识别错误，不要改变原意
2. 保持口语化风格，不要改成书面语
3. 保留原始的标点和断句
4. 数字、英文专业术语保持原样
5. 如果不确定是否为错别字，保留原文
6. 直接输出纠正后的文本，不要加解释"""

        user_prompt = f"""视频标题：{video_title}

请纠正以下逐字稿中的错别字：

{text}"""

        try:
            max_tokens = min(self.config.llm.max_tokens, 4096)
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{self.config.llm.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.llm.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.config.llm.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.1,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    fixed = data["choices"][0]["message"]["content"].strip()
                    return fixed if fixed else text
                else:
                    return text
        except Exception as e:
            print(f"[WARN] AI 纠错失败: {e}")
            return text

    def batch_fix_typos(self, progress_callback: Callable = None) -> dict:
        """批量对所有逐字稿进行 AI 纠错"""
        stats = {"total": 0, "fixed": 0, "skipped": 0, "failed": 0}

        videos = self.db.get_all_videos()
        stats["total"] = len(videos)

        for i, video in enumerate(videos):
            aweme_id = video['aweme_id']
            transcript = self.db.get_transcript(aweme_id)
            if not transcript or not transcript.get('transcript_text'):
                stats["skipped"] += 1
                continue

            text = transcript['transcript_text']

            # 检查是否已纠错（通过检查是否有标记）
            if text.startswith("[FIXED]"):
                stats["skipped"] += 1
                continue

            if progress_callback:
                progress_callback(f"[{i+1}/{len(videos)}] AI纠错: {video.get('title', '')[:30]}...")

            fixed_text = self.fix_typos(text, video.get('title', ''))
            if fixed_text != text:
                # 加标记防止重复纠错
                fixed_text = "[FIXED]" + fixed_text
                # 更新数据库
                self.db._conn.execute(
                    "UPDATE transcripts SET transcript_text=? WHERE aweme_id=?",
                    (fixed_text, aweme_id)
                )
                # 更新文件
                txt_path = self.config.transcripts_path / f"{aweme_id}.txt"
                if txt_path.exists():
                    txt_path.write_text(fixed_text.replace("[FIXED]", ""), encoding="utf-8")
                stats["fixed"] += 1
            else:
                stats["skipped"] += 1

        self.db._conn.commit()
        return stats
