"""
定时调度模块
使用 APScheduler 实现间隔执行
"""
import time
from typing import Callable

from .config import AppConfig


class TaskScheduler:
    """任务调度器"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.scheduler = None

    def start(self, job_func: Callable):
        """启动定时任务"""
        if not self.config.scheduler.enabled:
            print("[INFO] 定时任务已禁用")
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            print("[WARN] apscheduler 未安装，定时任务不可用")
            return

        self.scheduler = BackgroundScheduler(timezone=self.config.scheduler.timezone)

        interval_hours = self.config.scheduler.interval_hours
        trigger = IntervalTrigger(hours=interval_hours)

        self.scheduler.add_job(
            job_func,
            trigger=trigger,
            id="douylike_pipeline",
            name=f"每{interval_hours}小时自动采集",
            replace_existing=True,
        )

        self.scheduler.start()
        print(f"[INFO] 定时任务已启动: 每 {interval_hours} 小时执行一次")

    def stop(self):
        """停止调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            self.scheduler = None

    def run_once(self, job_func: Callable):
        """手动执行一次任务"""
        print("[INFO] 手动触发任务...")
        job_func()
        print("[INFO] 任务完成")


def run_scheduled_mode(config: AppConfig, job_func: Callable):
    """运行定时模式（阻塞）"""
    scheduler = TaskScheduler(config)
    scheduler.start(job_func)

    interval = config.scheduler.interval_hours
    print(f"[INFO] 定时模式运行中，每 {interval} 小时执行一次，按 Ctrl+C 停止...")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[INFO] 正在停止...")
        scheduler.stop()
        print("[INFO] 已停止")
