"""
AI 多维度分析引擎
使用 LLM 对视频内容进行全维度分析
"""
import os
import json
import httpx
from pathlib import Path
from typing import Optional, Callable, List, Dict

from .config import AppConfig
from .database import Database


PROMPT_DIR = Path(__file__).parent.parent / "prompts"


class Analyzer:
    """AI 分析引擎"""

    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db

    def _load_prompt(self, name: str) -> str:
        """加载 prompt 模板"""
        prompt_path = PROMPT_DIR / f"{name}.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""

    def _call_llm(self, system_prompt: str, user_prompt: str,
                  temperature: float = None) -> Optional[str]:
        """调用 LLM API"""
        if not self.config.llm.api_key or self.config.llm.api_key == "your-api-key":
            return None

        headers = {
            "Authorization": f"Bearer {self.config.llm.api_key}",
            "Content-Type": "application/json",
        }
        # 限制 max_tokens 不超过模型上限
        max_tokens = min(self.config.llm.max_tokens, 4096)
        payload = {
            "model": self.config.llm.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature or self.config.llm.temperature,
        }

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{self.config.llm.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[ERROR] LLM 调用失败: {e}")
            return None

    def analyze_single_video(self, aweme_id: str,
                             progress_callback: Callable = None) -> Optional[Dict]:
        """
        单视频内容分析
        返回: 分析结果字典
        """
        # 检查是否已分析
        existing = self.db.get_analysis(aweme_id)
        if existing:
            if progress_callback:
                progress_callback(f"分析已存在，跳过: {aweme_id}")
            return existing

        # 获取视频信息
        video = self.db.get_video(aweme_id)
        if not video:
            return None

        # 获取逐字稿
        transcript = self.db.get_transcript(aweme_id)
        transcript_text = transcript.get('transcript_text', '') if transcript else ''

        if not transcript_text:
            if progress_callback:
                progress_callback(f"无逐字稿，跳过分析: {aweme_id}")
            return None

        # 加载 prompt
        system_prompt = self._load_prompt("analyze_video")
        if not system_prompt:
            system_prompt = """你是一位专业的短视频内容分析师。请根据以下视频信息和逐字稿，
从多个维度分析视频内容，输出结构化 JSON。"""

        # 构造分析请求
        user_prompt = f"""请分析以下抖音视频：

## 视频信息
- 标题: {video.get('title', '')}
- 作者: {video.get('author', '')}
- 描述: {video.get('description', '')}
- 标签: {video.get('tags', '[]')}
- 点赞: {video.get('like_count', 0)}
- 评论: {video.get('comment_count', 0)}
- 收藏: {video.get('collect_count', 0)}
- 转发: {video.get('share_count', 0)}

## 逐字稿
{transcript_text[:3000]}

请输出 JSON 格式的分析结果，包含以下字段：
{{
  "topic": "主题/话题",
  "content_type": "内容类型（教程/观点/故事/测评/娱乐/其他）",
  "target_audience": "目标受众画像",
  "hook_analysis": "开头钩子（Hook）分析",
  "content_structure": "内容结构拆解",
  "differentiation": "差异化卖点",
  "topic_angle": "选题角度分析",
  "ai_score": 0-10的AI综合评分,
  "ai_summary": "AI综合评价（200字内）",
  "improvement_suggestions": "改进建议",
  "viral_score": 0-10的爆款潜力评分
}}"""

        if progress_callback:
            progress_callback(f"AI 分析中: {video.get('title', '')[:30]}...")

        result_text = self._call_llm(system_prompt, user_prompt, temperature=0.3)
        if not result_text:
            return None

        # 解析 JSON
        try:
            # 尝试从 markdown 代码块中提取 JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            result = json.loads(result_text.strip())
        except json.JSONDecodeError:
            # 如果解析失败，保存原始文本
            result = {
                "topic": "",
                "content_type": "",
                "target_audience": "",
                "hook_analysis": "",
                "content_structure": "",
                "differentiation": "",
                "topic_angle": "",
                "ai_score": 0,
                "ai_summary": result_text[:500],
                "improvement_suggestions": "",
                "viral_score": 0,
            }

        # 保存到数据库
        self.db.save_analysis(aweme_id, result)

        # 保存分析报告到文件
        report_dir = self.config.reports_path
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{aweme_id}_analysis.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result

    def analyze_topics(self, progress_callback: Callable = None) -> List[Dict]:
        """
        跨视频选题趋势分析
        分析所有已分析视频的话题频率和趋势
        """
        if progress_callback:
            progress_callback("正在进行选题趋势分析...")

        # 获取所有分析结果
        all_videos = self.db.get_all_videos()
        analyzed_videos = []
        for v in all_videos:
            analysis = self.db.get_analysis(v['aweme_id'])
            if analysis:
                analyzed_videos.append({
                    "title": v.get('title', ''),
                    "topic": analysis.get('topic', ''),
                    "content_type": analysis.get('content_type', ''),
                    "ai_score": analysis.get('ai_score', 0),
                    "viral_score": analysis.get('viral_score', 0),
                    "like_count": v.get('like_count', 0),
                })

        if not analyzed_videos:
            return []

        system_prompt = """你是一位数据分析专家。请分析以下视频列表的话题分布和趋势，
识别热门话题、上升趋势、选题空白点。输出 JSON 格式。"""

        videos_text = "\n".join([
            f"- 标题: {v['title']}, 话题: {v['topic']}, 类型: {v['content_type']}, "
            f"AI评分: {v['ai_score']}, 爆款分: {v['viral_score']}, 点赞: {v['like_count']}"
            for v in analyzed_videos[:50]  # 最多分析50个
        ])

        user_prompt = f"""请分析以下视频数据：

{videos_text}

请输出 JSON 数组，每个元素包含：
{{
  "topic_name": "话题名称",
  "frequency": 出现次数,
  "trend_direction": "上升/稳定/下降",
  "heat_score": 0-10热度评分,
  "suggestions": ["选题建议1", "选题建议2"],
  "blank_points": ["选题空白点1", "选题空白点2"]
}}"""

        result_text = self._call_llm(system_prompt, user_prompt, temperature=0.3)
        if not result_text:
            return []

        try:
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            topics = json.loads(result_text.strip())
            if not isinstance(topics, list):
                topics = [topics]
        except json.JSONDecodeError:
            return []

        # 保存到数据库
        from datetime import datetime
        now = datetime.now().isoformat()
        for topic in topics:
            self.db._conn.execute("""
                INSERT INTO topics (topic_name, frequency, trend_direction,
                    heat_score, suggestions, blank_points, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                topic.get('topic_name', ''),
                topic.get('frequency', 0),
                topic.get('trend_direction', ''),
                topic.get('heat_score', 0),
                json.dumps(topic.get('suggestions', []), ensure_ascii=False),
                json.dumps(topic.get('blank_points', []), ensure_ascii=False),
                now,
            ))
        self.db._conn.commit()

        return topics

    def analyze_viral_formulas(self, progress_callback: Callable = None) -> List[Dict]:
        """
        爆款公式提炼
        从高互动视频中提炼可复制的爆款公式
        """
        if progress_callback:
            progress_callback("正在提炼爆款公式...")

        # 获取高互动视频
        all_videos = self.db.get_all_videos()
        high_engagement = sorted(
            [v for v in all_videos if v.get('like_count', 0) > 0],
            key=lambda x: x.get('like_count', 0),
            reverse=True
        )[:20]  # 取前20个高互动视频

        if not high_engagement:
            return []

        # 获取这些视频的分析和逐字稿
        video_details = []
        for v in high_engagement:
            analysis = self.db.get_analysis(v['aweme_id'])
            transcript = self.db.get_transcript(v['aweme_id'])
            video_details.append({
                "title": v.get('title', ''),
                "like_count": v.get('like_count', 0),
                "comment_count": v.get('comment_count', 0),
                "topic": analysis.get('topic', '') if analysis else '',
                "hook_analysis": analysis.get('hook_analysis', '') if analysis else '',
                "transcript_preview": (transcript.get('transcript_text', '')[:500] if transcript else ''),
            })

        system_prompt = """你是一位短视频运营专家。请从以下高互动视频数据中提炼爆款公式。
分析标题模式、钩子设计、内容结构、节奏把控等维度。输出 JSON 格式。"""

        details_text = "\n".join([
            f"- 标题: {d['title']}, 点赞: {d['like_count']}, 评论: {d['comment_count']}, "
            f"话题: {d['topic']}, 钩子: {d['hook_analysis']}"
            for d in video_details
        ])

        user_prompt = f"""请从以下高互动视频中提炼爆款公式：

{details_text}

请输出 JSON 数组，每个元素包含：
{{
  "formula_name": "公式名称",
  "applicable_scenario": "适用场景",
  "title_template": "标题模板/公式",
  "cover_rules": "封面设计规律",
  "content_rhythm": "内容节奏模式",
  "case_references": ["相关视频标题"]
}}"""

        result_text = self._call_llm(system_prompt, user_prompt, temperature=0.3)
        if not result_text:
            return []

        try:
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            formulas = json.loads(result_text.strip())
            if not isinstance(formulas, list):
                formulas = [formulas]
        except json.JSONDecodeError:
            return []

        # 保存到数据库
        from datetime import datetime
        now = datetime.now().isoformat()
        for f in formulas:
            self.db._conn.execute("""
                INSERT INTO viral_formulas (formula_name, applicable_scenario,
                    title_template, cover_rules, content_rhythm, case_references, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f.get('formula_name', ''),
                f.get('applicable_scenario', ''),
                f.get('title_template', ''),
                f.get('cover_rules', ''),
                f.get('content_rhythm', ''),
                json.dumps(f.get('case_references', []), ensure_ascii=False),
                now,
            ))
        self.db._conn.commit()

        return formulas

    def batch_analyze(self, progress_callback: Callable = None) -> dict:
        """
        批量分析所有已转写但未分析的视频
        """
        stats = {"total": 0, "analyzed": 0, "skipped": 0, "failed": 0}

        videos = self.db.get_all_videos()
        transcribed = [v for v in videos if v.get('downloaded')]

        stats["total"] = len(transcribed)

        for i, video in enumerate(transcribed):
            aweme_id = video['aweme_id']

            if self.db.video_analyzed(aweme_id):
                stats["skipped"] += 1
                continue

            # 检查是否有逐字稿
            if not self.db.video_transcribed(aweme_id):
                stats["skipped"] += 1
                continue

            if progress_callback:
                progress_callback(f"[{i+1}/{len(transcribed)}] 分析: {video.get('title', '')[:30]}...")

            result = self.analyze_single_video(aweme_id, progress_callback)
            if result:
                stats["analyzed"] += 1
            else:
                stats["failed"] += 1

        return stats
