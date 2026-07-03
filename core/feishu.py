"""
飞书多维表格同步模块
使用 lark-oapi SDK 操作飞书 Bitable
"""
import json
import time
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

try:
    import lark_oapi as lark
    from lark_oapi.api.bitable.v1 import *
    HAS_LARK_SDK = True
except ImportError:
    HAS_LARK_SDK = False

from .config import AppConfig, save_config
from .database import Database


# 多维表格字段定义（与飞书实际创建的字段名一致）
TABLE_DEFINITIONS = {
    "videos": {
        "name": "Videos",
        "fields": [
            {"field_name": "Video ID", "type": 1},
            {"field_name": "Title", "type": 1},
            {"field_name": "Author", "type": 1},
            {"field_name": "Video URL", "type": 15},
            {"field_name": "Likes", "type": 2},
            {"field_name": "Comments", "type": 2},
            {"field_name": "Favorites", "type": 2},
            {"field_name": "Shares", "type": 2},
            {"field_name": "Plays", "type": 2},
            {"field_name": "Duration(sec)", "type": 2},
            {"field_name": "Publish Time", "type": 5},
            {"field_name": "Collected At", "type": 5},
            {"field_name": "Description", "type": 1},
            {"field_name": "Tags", "type": 4},
            {"field_name": "BGM", "type": 1},
        ],
    },
    "transcripts": {
        "name": "Transcripts",
        "fields": [
            {"field_name": "Video ID", "type": 1},
            {"field_name": "Transcript", "type": 1},
            {"field_name": "Word Count", "type": 2},
            {"field_name": "Duration(sec)", "type": 2},
            {"field_name": "Extracted At", "type": 5},
        ],
    },
    "analysis": {
        "name": "AI Analysis",
        "fields": [
            {"field_name": "Video ID", "type": 1},
            {"field_name": "Topic", "type": 1},
            {"field_name": "Content Type", "type": 3},
            {"field_name": "Target Audience", "type": 1},
            {"field_name": "Hook Analysis", "type": 1},
            {"field_name": "Content Structure", "type": 1},
            {"field_name": "Differentiation", "type": 1},
            {"field_name": "Topic Angle", "type": 1},
            {"field_name": "AI Score", "type": 2},
            {"field_name": "Viral Score", "type": 2},
            {"field_name": "AI Summary", "type": 1},
            {"field_name": "Suggestions", "type": 1},
            {"field_name": "Analyzed At", "type": 5},
        ],
    },
    "topics": {
        "name": "Topic Analysis",
        "fields": [
            {"field_name": "Topic Name", "type": 1},
            {"field_name": "Frequency", "type": 2},
            {"field_name": "Trend", "type": 3},
            {"field_name": "Heat Score", "type": 2},
            {"field_name": "Suggestions", "type": 1},
            {"field_name": "Blank Points", "type": 1},
            {"field_name": "Analyzed At", "type": 5},
        ],
    },
    "competitors": {
        "name": "Competitors",
        "fields": [
            {"field_name": "Account", "type": 1},
            {"field_name": "Strategy", "type": 1},
            {"field_name": "Strengths", "type": 1},
            {"field_name": "Weaknesses", "type": 1},
            {"field_name": "Learnable Points", "type": 1},
            {"field_name": "Analyzed At", "type": 5},
        ],
    },
    "hotspots": {
        "name": "Hotspots",
        "fields": [
            {"field_name": "Keyword", "type": 1},
            {"field_name": "Platform", "type": 1},
            {"field_name": "Heat Index", "type": 2},
            {"field_name": "Trend Desc", "type": 1},
            {"field_name": "Related Videos", "type": 1},
            {"field_name": "Timeliness", "type": 3},
            {"field_name": "Analyzed At", "type": 5},
        ],
    },
    "logs": {
        "name": "System Logs",
        "fields": [
            {"field_name": "Run Time", "type": 5},
            {"field_name": "Task Type", "type": 3},
            {"field_name": "Total", "type": 2},
            {"field_name": "Success", "type": 2},
            {"field_name": "Failed", "type": 2},
            {"field_name": "Duration(sec)", "type": 2},
            {"field_name": "Error", "type": 1},
        ],
    },
}


class FeishuSync:
    """飞书多维表格同步器"""

    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db
        self.client = None

        if HAS_LARK_SDK:
            self.client = lark.Client.builder() \
                .app_id(config.feishu.app_id) \
                .app_secret(config.feishu.app_secret) \
                .build()

    def is_configured(self) -> bool:
        """检查飞书是否已配置"""
        return (
            HAS_LARK_SDK
            and self.config.feishu.app_id
            and self.config.feishu.app_id != "cli_xxxx"
            and self.config.feishu.app_secret
            and self.config.feishu.app_secret != "xxxx"
        )

    def setup_bitable(self) -> bool:
        """
        首次运行：创建多维表格 + 所有数据表
        返回: 是否成功
        """
        if not self.is_configured():
            print("[WARN] 飞书未配置，跳过")
            return False

        # 如果已有 app_token，跳过创建
        if self.config.feishu.bitable_app_token:
            print(f"[INFO] 飞书多维表格已存在: {self.config.feishu.bitable_app_token}")
            return True

        # 创建 Bitable App
        try:
            request = CreateAppRequest.builder() \
                .request_body(
                    ReqApp.builder()
                    .name("DOUYlike 数据中心")
                    .build()
                ).build()
            response = self.client.bitable.v1.app.create(request)

            if not response.success():
                print(f"[ERROR] 创建多维表格失败: {response.msg}")
                return False

            app_token = response.data.app.app_token
            self.config.feishu.bitable_app_token = app_token
            print(f"[INFO] 多维表格已创建: {app_token}")

            # 创建各数据表
            for table_key, table_def in TABLE_DEFINITIONS.items():
                table_id = self._create_table(app_token, table_def)
                if table_id:
                    setattr(self.config.feishu.table_ids, table_key, table_id)
                    print(f"[INFO] 数据表已创建: {table_def['name']} -> {table_id}")

            # 保存配置
            save_config(self.config)

            return True

        except Exception as e:
            print(f"[ERROR] 设置飞书多维表格失败: {e}")
            return False

    def _create_table(self, app_token: str, table_def: Dict) -> Optional[str]:
        """创建单个数据表"""
        try:
            fields = [
                AppTableCreateHeader.builder()
                .field_name(f["field_name"])
                .type(f["type"])
                .build()
                for f in table_def["fields"]
            ]

            request = CreateAppTableRequest.builder() \
                .app_token(app_token) \
                .request_body(
                    CreateAppTableRequestBody.builder()
                    .table(
                        ReqTable.builder()
                        .name(table_def["name"])
                        .fields(fields)
                        .build()
                    ).build()
                ).build()
            response = self.client.bitable.v1.app_table.create(request)

            if response.success():
                return response.data.table_id
            else:
                print(f"[ERROR] 创建表失败: {response.msg}")
                return None
        except Exception as e:
            print(f"[ERROR] 创建表异常: {e}")
            return None

    def sync_videos(self) -> dict:
        """同步视频数据到飞书"""
        stats = {"synced": 0, "failed": 0}
        if not self.is_configured() or not self.config.feishu.table_ids.videos:
            return stats

        unsynced = self.db.get_unsynced_videos()
        if not unsynced:
            return stats

        records = []
        for v in unsynced:
            record = {
                "Video ID": v.get("aweme_id", ""),
                "Title": v.get("title", ""),
                "Author": v.get("author", ""),
                "Video URL": {"text": "Open", "link": f"https://www.douyin.com/video/{v.get('aweme_id', '')}"},
                "Likes": v.get("like_count", 0),
                "Comments": v.get("comment_count", 0),
                "Favorites": v.get("collect_count", 0),
                "Shares": v.get("share_count", 0),
                "Plays": v.get("play_count", 0),
                "Duration(sec)": v.get("duration", 0) / 1000 if v.get("duration", 0) > 1000 else v.get("duration", 0),
                "Description": v.get("description", ""),
                "BGM": v.get("music_title", ""),
            }
            # 时间戳转换
            if v.get("create_time"):
                record["Publish Time"] = int(v["create_time"]) * 1000
            if v.get("collected_at"):
                try:
                    dt = datetime.fromisoformat(v["collected_at"])
                    record["Collected At"] = int(dt.timestamp() * 1000)
                except Exception:
                    pass
            # 标签 (飞书多选字段需要字符串数组)
            tags = v.get("tags", "[]")
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []
            if tags and isinstance(tags, list):
                record["Tags"] = [str(t) for t in tags]

            records.append(record)

        # 批量创建（每次最多500条）
        for i in range(0, len(records), 500):
            batch = records[i:i+500]
            try:
                request = BatchCreateAppTableRecordRequest.builder() \
                    .app_token(self.config.feishu.bitable_app_token) \
                    .table_id(self.config.feishu.table_ids.videos) \
                    .request_body(
                        BatchCreateAppTableRecordRequestBody.builder()
                        .records([
                            AppTableRecord.builder().fields(r).build()
                            for r in batch
                        ]).build()
                    ).build()
                response = self.client.bitable.v1.app_table_record.batch_create(request)

                if response.success():
                    # 标记已同步
                    for j, v in enumerate(unsynced[i:i+500]):
                        record_id = response.data.records[j].record_id if j < len(response.data.records) else ""
                        self.db.mark_synced("videos", v["aweme_id"], record_id)
                    stats["synced"] += len(batch)
                else:
                    print(f"[ERROR] 批量创建失败: {response.msg}")
                    stats["failed"] += len(batch)
            except Exception as e:
                print(f"[ERROR] 同步视频异常: {e}")
                stats["failed"] += len(batch)

            time.sleep(0.2)  # 限流

        return stats

    def sync_transcripts(self) -> dict:
        """同步逐字稿到飞书"""
        stats = {"synced": 0, "failed": 0}
        if not self.is_configured() or not self.config.feishu.table_ids.transcripts:
            return stats

        unsynced = self.db.get_unsynced_transcripts()
        if not unsynced:
            return stats

        records = []
        for t in unsynced:
            records.append({
                "Video ID": t.get("aweme_id", ""),
                "Transcript": t.get("transcript_text", "")[:10000],
                "Word Count": t.get("word_count", 0),
                "Duration(sec)": t.get("duration_seconds", 0),
            })

        for i in range(0, len(records), 500):
            batch = records[i:i+500]
            try:
                request = BatchCreateAppTableRecordRequest.builder() \
                    .app_token(self.config.feishu.bitable_app_token) \
                    .table_id(self.config.feishu.table_ids.transcripts) \
                    .request_body(
                        BatchCreateAppTableRecordRequestBody.builder()
                        .records([
                            AppTableRecord.builder().fields(r).build()
                            for r in batch
                        ]).build()
                    ).build()
                response = self.client.bitable.v1.app_table_record.batch_create(request)

                if response.success():
                    for j, t in enumerate(unsynced[i:i+500]):
                        record_id = response.data.records[j].record_id if j < len(response.data.records) else ""
                        self.db.mark_synced("transcripts", t["aweme_id"], record_id)
                    stats["synced"] += len(batch)
                else:
                    stats["failed"] += len(batch)
            except Exception as e:
                print(f"[ERROR] 同步逐字稿异常: {e}")
                stats["failed"] += len(batch)

            time.sleep(0.2)

        return stats

    def sync_analysis(self) -> dict:
        """同步 AI 分析结果到飞书"""
        stats = {"synced": 0, "failed": 0}
        if not self.is_configured() or not self.config.feishu.table_ids.analysis:
            return stats

        unsynced = self.db.get_unsynced_analysis()
        if not unsynced:
            return stats

        records = []
        for a in unsynced:
            records.append({
                "Video ID": a.get("aweme_id", ""),
                "Topic": a.get("topic", ""),
                "Content Type": a.get("content_type", ""),
                "Target Audience": a.get("target_audience", ""),
                "Hook Analysis": a.get("hook_analysis", ""),
                "Content Structure": a.get("content_structure", ""),
                "Differentiation": a.get("differentiation", ""),
                "Topic Angle": a.get("topic_angle", ""),
                "AI Score": a.get("ai_score", 0),
                "Viral Score": a.get("viral_score", 0),
                "AI Summary": a.get("ai_summary", ""),
                "Suggestions": a.get("improvement_suggestions", ""),
            })

        for i in range(0, len(records), 500):
            batch = records[i:i+500]
            try:
                request = BatchCreateAppTableRecordRequest.builder() \
                    .app_token(self.config.feishu.bitable_app_token) \
                    .table_id(self.config.feishu.table_ids.analysis) \
                    .request_body(
                        BatchCreateAppTableRecordRequestBody.builder()
                        .records([
                            AppTableRecord.builder().fields(r).build()
                            for r in batch
                        ]).build()
                    ).build()
                response = self.client.bitable.v1.app_table_record.batch_create(request)

                if response.success():
                    for j, a in enumerate(unsynced[i:i+500]):
                        record_id = response.data.records[j].record_id if j < len(response.data.records) else ""
                        self.db.mark_synced("analysis", a["aweme_id"], record_id)
                    stats["synced"] += len(batch)
                else:
                    stats["failed"] += len(batch)
            except Exception as e:
                print(f"[ERROR] 同步分析异常: {e}")
                stats["failed"] += len(batch)

            time.sleep(0.2)

        return stats

    def sync_all(self, progress_callback: Callable = None) -> dict:
        """同步所有数据到飞书"""
        total_stats = {"videos": {}, "transcripts": {}, "analysis": {}}

        if progress_callback:
            progress_callback("同步视频数据...")
        total_stats["videos"] = self.sync_videos()

        if progress_callback:
            progress_callback("同步逐字稿...")
        total_stats["transcripts"] = self.sync_transcripts()

        if progress_callback:
            progress_callback("同步分析结果...")
        total_stats["analysis"] = self.sync_analysis()

        return total_stats
