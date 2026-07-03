"""
DOUYlike - 抖音收藏夹自动更新系统
主入口：支持 CLI 和定时模式
"""
import sys
import argparse
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from core.config import load_config
from core.pipeline import Pipeline
from core.scheduler import TaskScheduler, run_scheduled_mode


def cmd_run(args):
    """执行完整流水线"""
    config = load_config(args.config)
    steps = args.steps.split(",") if args.steps else None

    pipeline = Pipeline(config)
    results = pipeline.run(steps=steps, progress_callback=print)

    if not results["success"]:
        print(f"\n[FAIL] {results['error']}")
        sys.exit(1)


def cmd_collect(args):
    """仅采集收藏夹"""
    config = load_config(args.config)
    pipeline = Pipeline(config)
    results = pipeline.run(steps=["collect"], progress_callback=print)


def cmd_transcribe(args):
    """仅转写逐字稿"""
    config = load_config(args.config)
    pipeline = Pipeline(config)
    results = pipeline.run(steps=["transcribe"], progress_callback=print)


def cmd_analyze(args):
    """仅 AI 分析"""
    config = load_config(args.config)
    pipeline = Pipeline(config)
    results = pipeline.run(steps=["analyze"], progress_callback=print)


def cmd_fix_typos(args):
    """AI 纠错逐字稿"""
    config = load_config(args.config)
    from core.database import Database
    from core.transcriber import TranscriptExtractor
    db = Database(config)
    db.connect()
    te = TranscriptExtractor(config, db)
    stats = te.batch_fix_typos(progress_callback=print)
    print(f"\n纠错完成: 总计 {stats['total']}, 纠错 {stats['fixed']}, 跳过 {stats['skipped']}")
    db.close()


def cmd_sync(args):
    """仅同步飞书"""
    config = load_config(args.config)
    pipeline = Pipeline(config)
    results = pipeline.run(steps=["sync"], progress_callback=print)


def cmd_stats(args):
    """查看统计信息"""
    from core.database import Database
    config = load_config(args.config)
    db = Database(config)
    db.connect()

    stats = db.get_stats()
    print("\n📊 DOUYlike 数据统计")
    print("=" * 40)
    print(f"  视频总数:   {stats['total_videos']}")
    print(f"  已下载:     {stats['downloaded']}")
    print(f"  已转写:     {stats['transcribed']}")
    print(f"  已分析:     {stats['analyzed']}")
    print(f"  已同步飞书: {stats['synced_feishu']}")
    print("=" * 40)

    db.close()


def cmd_serve(args):
    """定时任务模式"""
    config = load_config(args.config)
    pipeline = Pipeline(config)

    def job():
        pipeline.run(progress_callback=print)

    if args.once:
        # 手动执行一次
        scheduler = TaskScheduler(config)
        scheduler.run_once(job)
    else:
        # 定时模式
        run_scheduled_mode(config, job)


def cmd_setup_feishu(args):
    """设置飞书多维表格"""
    from core.database import Database
    from core.feishu import FeishuSync

    config = load_config(args.config)
    db = Database(config)
    db.connect()

    feishu = FeishuSync(config, db)
    if feishu.is_configured():
        print("正在创建飞书多维表格...")
        success = feishu.setup_bitable()
        if success:
            print("[OK] Done")
        else:
            print("[FAIL] Setup failed")
            sys.exit(1)
    else:
        print("[FAIL] Feishu not configured")
        sys.exit(1)

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="DOUYlike - 抖音收藏夹自动更新系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py run                    # 执行完整流水线
  python main.py run --steps collect    # 仅采集收藏夹
  python main.py run --steps collect,transcribe  # 采集+转写
  python main.py serve                  # 启动定时任务
  python main.py serve --once           # 手动执行一次
  python main.py stats                  # 查看统计信息
  python main.py setup-feishu           # 设置飞书多维表格
        """
    )
    parser.add_argument("--config", "-c", default="config.yaml", help="配置文件路径")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # run
    run_parser = subparsers.add_parser("run", help="执行流水线")
    run_parser.add_argument("--steps", "-s", help="指定步骤 (collect,transcribe,analyze,sync)")
    run_parser.set_defaults(func=cmd_run)

    # collect
    collect_parser = subparsers.add_parser("collect", help="仅采集收藏夹")
    collect_parser.set_defaults(func=cmd_collect)

    # transcribe
    transcribe_parser = subparsers.add_parser("transcribe", help="仅转写逐字稿")
    transcribe_parser.set_defaults(func=cmd_transcribe)

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="仅 AI 分析")
    analyze_parser.set_defaults(func=cmd_analyze)

    # fix-typos
    fix_parser = subparsers.add_parser("fix-typos", help="AI 纠错逐字稿")
    fix_parser.set_defaults(func=cmd_fix_typos)

    # sync
    sync_parser = subparsers.add_parser("sync", help="仅同步飞书")
    sync_parser.set_defaults(func=cmd_sync)

    # stats
    stats_parser = subparsers.add_parser("stats", help="查看统计信息")
    stats_parser.set_defaults(func=cmd_stats)

    # serve
    serve_parser = subparsers.add_parser("serve", help="定时任务模式")
    serve_parser.add_argument("--once", action="store_true", help="手动执行一次")
    serve_parser.set_defaults(func=cmd_serve)

    # setup-feishu
    feishu_parser = subparsers.add_parser("setup-feishu", help="设置飞书多维表格")
    feishu_parser.set_defaults(func=cmd_setup_feishu)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
