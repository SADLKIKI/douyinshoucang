"""
处理流水线模块
编排完整的采集 → 转写 → 分析 → 同步流程
"""
import time
import traceback
from typing import Callable, Optional
from datetime import datetime

from .config import AppConfig
from .database import Database
from .collector import DouyinCollector
from .downloader import VideoDownloader
from .transcriber import TranscriptExtractor
from .analyzer import Analyzer
from .feishu import FeishuSync


class Pipeline:
    """完整处理流水线"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.db = Database(config)
        self.collector = DouyinCollector(config)
        self.downloader = VideoDownloader(config, self.db)
        self.transcriber = TranscriptExtractor(config, self.db)
        self.analyzer = Analyzer(config, self.db)
        self.feishu = FeishuSync(config, self.db)

    def run(self, steps: Optional[list] = None,
            progress_callback: Callable = None) -> dict:
        """
        运行完整流水线
        steps: 可选，指定运行哪些步骤 ["collect", "transcribe", "analyze", "sync"]
        progress_callback: 进度回调函数
        """
        if steps is None:
            steps = ["collect", "transcribe", "analyze", "sync"]

        start_time = time.time()
        results = {"steps": {}, "total_time": 0, "success": True, "error": ""}

        def log(msg):
            if progress_callback:
                progress_callback(msg)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

        try:
            # 初始化数据库
            log("初始化数据库...")
            self.db.connect()

            # 检查 Chrome 连接
            if "collect" in steps:
                log("检查 Chrome 连接...")
                if not self.collector.connect():
                    results["success"] = False
                    results["error"] = "无法连接到 Chrome，请确保 Chrome 已启动并开启了远程调试"
                    log(f"[X] {results['error']}")
                    return results

                if not self.collector.check_login():
                    results["success"] = False
                    results["error"] = "Chrome 未登录抖音"
                    log(f"[X] {results['error']}")
                    self.collector.disconnect()
                    return results

                log("[OK] Chrome 已连接并登录")

            # Step 1: 采集收藏夹
            if "collect" in steps:
                log("\n[1] Step 1: 采集收藏夹...")
                collect_stats = self.downloader.download_collection(
                    self.collector,
                    progress_callback=lambda msg, *a: log(f"  {msg}")
                )
                results["steps"]["collect"] = collect_stats
                log(f"  采集完成: 总计 {collect_stats['total']}个, "
                    f"新增 {collect_stats['new']}个, "
                    f"下载 {collect_stats['downloaded']}个, "
                    f"跳过 {collect_stats['skipped']}个")

                self.collector.disconnect()

            # Step 2: 逐字稿提取
            if "transcribe" in steps:
                log("\n[2] Step 2: 提取逐字稿...")
                transcribe_stats = self.transcriber.batch_transcribe(
                    progress_callback=lambda msg: log(f"  {msg}")
                )
                results["steps"]["transcribe"] = transcribe_stats
                log(f"  转写完成: 总计 {transcribe_stats['total']}个, "
                    f"成功 {transcribe_stats['success']}个, "
                    f"跳过 {transcribe_stats['skipped']}个, "
                    f"失败 {transcribe_stats['failed']}个")

            # Step 3: AI 分析
            if "analyze" in steps:
                log("\n[3] Step 3: AI 分析...")
                analyze_stats = self.analyzer.batch_analyze(
                    progress_callback=lambda msg: log(f"  {msg}")
                )
                results["steps"]["analyze"] = analyze_stats
                log(f"  分析完成: 总计 {analyze_stats['total']}个, "
                    f"分析 {analyze_stats['analyzed']}个, "
                    f"跳过 {analyze_stats['skipped']}个, "
                    f"失败 {analyze_stats['failed']}个")

                # 选题趋势分析
                log("\n[3.5] Step 3.5: 选题趋势分析...")
                topics = self.analyzer.analyze_topics(
                    progress_callback=lambda msg: log(f"  {msg}")
                )
                results["steps"]["topics"] = {"count": len(topics)}
                log(f"  选题分析完成: {len(topics)}个话题")

                # 爆款公式提炼
                log("\n[3.6] Step 3.6: 爆款公式提炼...")
                formulas = self.analyzer.analyze_viral_formulas(
                    progress_callback=lambda msg: log(f"  {msg}")
                )
                results["steps"]["viral_formulas"] = {"count": len(formulas)}
                log(f"  爆款公式完成: {len(formulas)}个公式")

            # Step 4: 飞书同步
            if "sync" in steps:
                log("\n[4] Step 4: 飞书同步...")
                if self.feishu.is_configured():
                    # 首次运行时自动创建表格
                    if not self.config.feishu.bitable_app_token:
                        log("  首次运行，创建飞书多维表格...")
                        self.feishu.setup_bitable()

                    sync_stats = self.feishu.sync_all(
                        progress_callback=lambda msg: log(f"  {msg}")
                    )
                    results["steps"]["sync"] = sync_stats
                    log(f"  同步完成: 视频 {sync_stats['videos'].get('synced', 0)}条, "
                        f"逐字稿 {sync_stats['transcripts'].get('synced', 0)}条, "
                        f"分析 {sync_stats['analysis'].get('synced', 0)}条")
                else:
                    log("  [!] 飞书未配置，跳过同步")
                    results["steps"]["sync"] = {"skipped": True}

            # 记录运行日志
            elapsed = time.time() - start_time
            results["total_time"] = elapsed
            self.db.log_run(
                task_type="pipeline",
                total=results["steps"].get("collect", {}).get("total", 0),
                success=results["steps"].get("transcribe", {}).get("success", 0),
                fail=results["steps"].get("transcribe", {}).get("failed", 0),
                duration=elapsed,
            )

            log(f"\n[OK] 流水线完成! 耗时: {elapsed:.1f}秒")

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)
            log(f"\n[X] 流水线异常: {e}")
            traceback.print_exc()

        finally:
            try:
                self.db.close()
            except Exception:
                pass

        return results
