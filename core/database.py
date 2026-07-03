"""
SQLite 本地数据库模块
管理视频数据、逐字稿、分析结果的本地存储
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from .config import AppConfig


class Database:
    """本地 SQLite 数据库"""

    def __init__(self, config: AppConfig):
        self.db_path = config.db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """建立连接"""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_tables(self):
        """初始化数据表"""
        self._conn.executescript("""
            -- 视频数据表
            CREATE TABLE IF NOT EXISTS videos (
                aweme_id TEXT PRIMARY KEY,
                title TEXT,
                author TEXT,
                author_id TEXT,
                author_avatar TEXT,
                cover_url TEXT,
                video_url TEXT,
                duration INTEGER,
                create_time INTEGER,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                collect_count INTEGER DEFAULT 0,
                play_count INTEGER DEFAULT 0,
                description TEXT,
                tags TEXT,                     -- JSON array
                music_title TEXT,
                music_author TEXT,
                downloaded INTEGER DEFAULT 0,
                video_path TEXT,
                cover_path TEXT,
                collected_at TEXT,
                updated_at TEXT,
                synced_feishu INTEGER DEFAULT 0,
                feishu_record_id TEXT
            );

            -- 逐字稿表
            CREATE TABLE IF NOT EXISTS transcripts (
                aweme_id TEXT PRIMARY KEY,
                transcript_text TEXT,
                srt_text TEXT,
                key_sentences TEXT,            -- JSON array
                word_count INTEGER,
                duration_seconds REAL,
                extracted_at TEXT,
                synced_feishu INTEGER DEFAULT 0,
                feishu_record_id TEXT
            );

            -- AI 分析表
            CREATE TABLE IF NOT EXISTS analysis (
                aweme_id TEXT PRIMARY KEY,
                topic TEXT,                    -- 主题/话题
                content_type TEXT,             -- 内容类型
                target_audience TEXT,          -- 目标受众
                hook_analysis TEXT,            -- 钩子分析
                content_structure TEXT,        -- 内容结构
                differentiation TEXT,          -- 差异化卖点
                topic_angle TEXT,              -- 选题角度
                ai_score REAL,                 -- AI 综合评分
                ai_summary TEXT,               -- AI 综合评价
                improvement_suggestions TEXT,  -- 改进建议
                viral_score REAL,              -- 爆款潜力评分
                full_analysis TEXT,            -- 完整分析 JSON
                analyzed_at TEXT,
                synced_feishu INTEGER DEFAULT 0,
                feishu_record_id TEXT
            );

            -- 选题分析表
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_name TEXT,
                frequency INTEGER DEFAULT 0,
                trend_direction TEXT,          -- 上升/稳定/下降
                heat_score REAL,
                suggestions TEXT,              -- JSON array
                blank_points TEXT,             -- JSON array - 选题空白点
                related_videos TEXT,           -- JSON array - aweme_id 列表
                analyzed_at TEXT,
                synced_feishu INTEGER DEFAULT 0,
                feishu_record_id TEXT
            );

            -- 爆款公式表
            CREATE TABLE IF NOT EXISTS viral_formulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formula_name TEXT,
                applicable_scenario TEXT,
                title_template TEXT,
                cover_rules TEXT,
                content_rhythm TEXT,
                case_references TEXT,          -- JSON array - aweme_id 列表
                analyzed_at TEXT,
                synced_feishu INTEGER DEFAULT 0,
                feishu_record_id TEXT
            );

            -- 热点趋势表
            CREATE TABLE IF NOT EXISTS hotspots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT,
                platform TEXT,
                heat_index REAL,
                trend_data TEXT,               -- JSON object
                related_videos TEXT,           -- JSON array
                time_sensitivity TEXT,         -- 时效性描述
                analyzed_at TEXT,
                synced_feishu INTEGER DEFAULT 0,
                feishu_record_id TEXT
            );

            -- 系统日志表
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_time TEXT,
                task_type TEXT,
                total_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                error_message TEXT,
                duration_seconds REAL,
                synced_feishu INTEGER DEFAULT 0,
                feishu_record_id TEXT
            );
        """)
        self._conn.commit()

    # ===== 视频操作 =====

    def video_exists(self, aweme_id: str) -> bool:
        """检查视频是否已存在"""
        row = self._conn.execute("SELECT 1 FROM videos WHERE aweme_id=?", (aweme_id,)).fetchone()
        return row is not None

    def video_downloaded(self, aweme_id: str) -> bool:
        """检查视频是否已下载"""
        row = self._conn.execute("SELECT downloaded FROM videos WHERE aweme_id=?", (aweme_id,)).fetchone()
        return row is not None and row["downloaded"] == 1

    def video_analyzed(self, aweme_id: str) -> bool:
        """检查视频是否已分析"""
        row = self._conn.execute("SELECT 1 FROM analysis WHERE aweme_id=?", (aweme_id,)).fetchone()
        return row is not None

    def video_transcribed(self, aweme_id: str) -> bool:
        """检查视频是否已转写"""
        row = self._conn.execute("SELECT 1 FROM transcripts WHERE aweme_id=?", (aweme_id,)).fetchone()
        return row is not None

    def insert_video(self, data: Dict[str, Any]):
        """插入或更新视频记录"""
        now = datetime.now().isoformat()
        tags = json.dumps(data.get("tags", []), ensure_ascii=False)

        self._conn.execute("""
            INSERT INTO videos (aweme_id, title, author, author_id, author_avatar,
                cover_url, video_url, duration, create_time,
                like_count, comment_count, share_count, collect_count, play_count,
                description, tags, music_title, music_author,
                downloaded, video_path, cover_path, collected_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(aweme_id) DO UPDATE SET
                title=excluded.title, like_count=excluded.like_count,
                comment_count=excluded.comment_count, share_count=excluded.share_count,
                collect_count=excluded.collect_count, play_count=excluded.play_count,
                description=excluded.description, tags=excluded.tags,
                updated_at=excluded.updated_at
        """, (
            data.get("aweme_id"), data.get("title", ""),
            data.get("author", ""), data.get("author_id", ""),
            data.get("author_avatar", ""),
            data.get("cover_url", ""), data.get("video_url", ""),
            data.get("duration", 0), data.get("create_time", 0),
            data.get("like_count", 0), data.get("comment_count", 0),
            data.get("share_count", 0), data.get("collect_count", 0),
            data.get("play_count", 0),
            data.get("description", ""), tags,
            data.get("music_title", ""), data.get("music_author", ""),
            1 if data.get("downloaded") else 0,
            data.get("video_path", ""), data.get("cover_path", ""),
            now, now
        ))
        self._conn.commit()

    def mark_downloaded(self, aweme_id: str, video_path: str, cover_path: str = ""):
        """标记视频已下载"""
        now = datetime.now().isoformat()
        self._conn.execute("""
            UPDATE videos SET downloaded=1, video_path=?, cover_path=?, updated_at=?
            WHERE aweme_id=?
        """, (video_path, cover_path, now, aweme_id))
        self._conn.commit()

    def mark_synced(self, table: str, aweme_id: str, feishu_record_id: str):
        """标记已同步到飞书"""
        self._conn.execute(f"""
            UPDATE {table} SET synced_feishu=1, feishu_record_id=?
            WHERE aweme_id=?
        """, (feishu_record_id, aweme_id))
        self._conn.commit()

    def get_unsynced_videos(self) -> List[Dict]:
        """获取未同步到飞书的视频"""
        rows = self._conn.execute(
            "SELECT * FROM videos WHERE synced_feishu=0"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unsynced_transcripts(self) -> List[Dict]:
        """获取未同步的逐字稿"""
        rows = self._conn.execute(
            "SELECT * FROM transcripts WHERE synced_feishu=0"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unsynced_analysis(self) -> List[Dict]:
        """获取未同步的分析"""
        rows = self._conn.execute(
            "SELECT * FROM analysis WHERE synced_feishu=0"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_videos(self) -> List[Dict]:
        """获取所有视频"""
        rows = self._conn.execute("SELECT * FROM videos ORDER BY collected_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_video(self, aweme_id: str) -> Optional[Dict]:
        """获取单个视频"""
        row = self._conn.execute("SELECT * FROM videos WHERE aweme_id=?", (aweme_id,)).fetchone()
        return dict(row) if row else None

    def get_transcript(self, aweme_id: str) -> Optional[Dict]:
        """获取逐字稿"""
        row = self._conn.execute("SELECT * FROM transcripts WHERE aweme_id=?", (aweme_id,)).fetchone()
        return dict(row) if row else None

    def get_analysis(self, aweme_id: str) -> Optional[Dict]:
        """获取分析结果"""
        row = self._conn.execute("SELECT * FROM analysis WHERE aweme_id=?", (aweme_id,)).fetchone()
        return dict(row) if row else None

    # ===== 逐字稿操作 =====

    def save_transcript(self, aweme_id: str, transcript_text: str,
                        srt_text: str = "", key_sentences: List[str] = None,
                        word_count: int = 0, duration_seconds: float = 0):
        """保存逐字稿"""
        now = datetime.now().isoformat()
        key_sentences_json = json.dumps(key_sentences or [], ensure_ascii=False)

        self._conn.execute("""
            INSERT INTO transcripts (aweme_id, transcript_text, srt_text,
                key_sentences, word_count, duration_seconds, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(aweme_id) DO UPDATE SET
                transcript_text=excluded.transcript_text,
                srt_text=excluded.srt_text,
                key_sentences=excluded.key_sentences,
                word_count=excluded.word_count,
                duration_seconds=excluded.duration_seconds,
                extracted_at=excluded.extracted_at
        """, (aweme_id, transcript_text, srt_text, key_sentences_json,
              word_count, duration_seconds, now))
        self._conn.commit()

    # ===== 分析操作 =====

    def save_analysis(self, aweme_id: str, data: Dict[str, Any]):
        """保存分析结果"""
        now = datetime.now().isoformat()
        full_analysis = json.dumps(data, ensure_ascii=False)

        # 确保所有字段都是基本类型（LLM 可能返回 dict）
        def to_str(v):
            if v is None: return ""
            if isinstance(v, (dict, list)): return json.dumps(v, ensure_ascii=False)
            return str(v)
        def to_float(v):
            if v is None: return 0
            try: return float(v)
            except: return 0

        self._conn.execute("""
            INSERT INTO analysis (aweme_id, topic, content_type, target_audience,
                hook_analysis, content_structure, differentiation, topic_angle,
                ai_score, ai_summary, improvement_suggestions, viral_score,
                full_analysis, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(aweme_id) DO UPDATE SET
                topic=excluded.topic, content_type=excluded.content_type,
                target_audience=excluded.target_audience,
                hook_analysis=excluded.hook_analysis,
                content_structure=excluded.content_structure,
                differentiation=excluded.differentiation,
                topic_angle=excluded.topic_angle,
                ai_score=excluded.ai_score,
                ai_summary=excluded.ai_summary,
                improvement_suggestions=excluded.improvement_suggestions,
                viral_score=excluded.viral_score,
                full_analysis=excluded.full_analysis,
                analyzed_at=excluded.analyzed_at
        """, (
            aweme_id, to_str(data.get("topic")), to_str(data.get("content_type")),
            to_str(data.get("target_audience")),
            to_str(data.get("hook_analysis")), to_str(data.get("content_structure")),
            to_str(data.get("differentiation")), to_str(data.get("topic_angle")),
            to_float(data.get("ai_score")), to_str(data.get("ai_summary")),
            to_str(data.get("improvement_suggestions")), to_float(data.get("viral_score")),
            full_analysis, now
        ))
        self._conn.commit()

    # ===== 日志操作 =====

    def log_run(self, task_type: str, total: int, success: int, fail: int,
                error: str = "", duration: float = 0):
        """记录运行日志"""
        now = datetime.now().isoformat()
        self._conn.execute("""
            INSERT INTO system_logs (run_time, task_type, total_count,
                success_count, fail_count, error_message, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (now, task_type, total, success, fail, error, duration))
        self._conn.commit()

    # ===== 统计查询 =====

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            "total_videos": self._conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0],
            "downloaded": self._conn.execute("SELECT COUNT(*) FROM videos WHERE downloaded=1").fetchone()[0],
            "transcribed": self._conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0],
            "analyzed": self._conn.execute("SELECT COUNT(*) FROM analysis").fetchone()[0],
            "synced_feishu": self._conn.execute("SELECT COUNT(*) FROM videos WHERE synced_feishu=1").fetchone()[0],
        }
