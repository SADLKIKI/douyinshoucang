"""
视频下载模块
封装下载逻辑，与数据库交互
"""
import os
from typing import Optional
from .config import AppConfig
from .database import Database
from .collector import DouyinCollector


class VideoDownloader:
    """视频下载管理器"""

    def __init__(self, config: AppConfig, db: Database):
        self.config = config
        self.db = db

    def download_collection(self, collector: DouyinCollector,
                            progress_callback=None) -> dict:
        """
        下载收藏夹中的新视频
        返回: {"total": N, "new": N, "downloaded": N, "skipped": N}
        """
        stats = {"total": 0, "new": 0, "downloaded": 0, "skipped": 0}

        # 1. 采集收藏夹列表
        if progress_callback:
            progress_callback("正在采集收藏夹列表...")

        videos = collector.collect_collection(progress_callback)
        stats["total"] = len(videos)

        if not videos:
            return stats

        # 2. 逐个处理
        for i, video in enumerate(videos):
            aweme_id = video.get('aweme_id', '')
            if not aweme_id:
                continue

            # 检查是否已存在
            if self.db.video_downloaded(aweme_id):
                stats["skipped"] += 1
                # 但仍更新互动数据
                self.db.insert_video(video)
                continue

            # 新视频
            stats["new"] += 1

            # 保存视频元数据到数据库
            self.db.insert_video(video)

            # 下载视频文件
            if progress_callback:
                progress_callback(f"[{i+1}/{len(videos)}] 下载: {video.get('title', '')[:30]}...")

            video_path = collector.download_video(video, str(self.config.downloads_path))

            if video_path:
                # 下载封面
                cover_path = collector.download_cover(video, str(self.config.downloads_path))

                # 标记已下载
                self.db.mark_downloaded(
                    aweme_id,
                    video_path,
                    cover_path or ""
                )
                stats["downloaded"] += 1
            else:
                # 下载失败，记录但不标记
                if progress_callback:
                    progress_callback(f"  [!] 下载失败: {video.get('title', '')[:30]}")

        return stats

    def download_single(self, collector: DouyinCollector,
                        aweme_id: str) -> bool:
        """下载单个视频"""
        # 获取视频信息
        video_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={aweme_id}&aid=6383&cookie_enabled=true"
        result = collector.fetch_api(video_url)

        if not result or not result.get('aweme_detail'):
            return False

        video = collector.extract_video_info(result['aweme_detail'])
        video['aweme_id'] = aweme_id

        # 保存到数据库
        self.db.insert_video(video)

        # 下载文件
        video_path = collector.download_video(video, str(self.config.downloads_path))
        if video_path:
            cover_path = collector.download_cover(video, str(self.config.downloads_path))
            self.db.mark_downloaded(aweme_id, video_path, cover_path or "")
            return True

        return False
