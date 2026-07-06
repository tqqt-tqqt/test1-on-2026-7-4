"""基于 Python schedule 库的调度器（开发/备选方案）。

生产环境推荐使用 Windows Task Scheduler（见 scripts/install_scheduled_task.ps1）。
"""

import time
import logging

logger = logging.getLogger(__name__)


def run_scheduler(
    config_path: str = "config.json",
    run_time: str = "16:00",
):
    """启动一个常驻进程，每天在指定时间运行生成任务。

    Args:
        config_path: 配置文件路径
        run_time: 每天运行时间（HH:MM 格式，如 "16:00"）

    注意：此进程需要持续运行。推荐用于开发测试场景；
    生产环境建议用 Windows Task Scheduler。
    """
    import schedule
    from .daily_runner import run_daily

    def job():
        logger.info("⏰ 定时任务触发: %s", run_time)
        try:
            result = run_daily(config_path=config_path)
            logger.info(
                "任务完成: %d/%d 篇文案生成成功",
                result["success"],
                result["total"],
            )
        except Exception as exc:
            logger.error("定时任务执行失败: %s", exc)

    schedule.every().day.at(run_time).do(job)
    logger.info("调度器已启动，每天 %s 执行。按 Ctrl+C 停止。", run_time)
    logger.info("下一次执行: %s", schedule.next_run())

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("调度器已停止。")


def run_once(config_path: str = "config.json", date_str: str = None, dry_run: bool = False):
    """运行一次生成任务（用于手动触发或 CLI 调用）。

    Returns:
        运行结果字典
    """
    from .daily_runner import run_daily

    return run_daily(config_path=config_path, date_str=date_str, dry_run=dry_run)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="小红书文案调度器")
    parser.add_argument("--run-once", action="store_true", help="运行一次后退出")
    parser.add_argument("--daemon", action="store_true", help="以守护进程模式运行（每天定时）")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--date", default=None, help="目标日期 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="仅输出到控制台")
    parser.add_argument("--time", default="16:00", help="每日运行时间（仅 daemon 模式）")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.run_once:
        result = run_once(config_path=args.config, date_str=args.date, dry_run=args.dry_run)
        print(f"\n生成完成: {result['success']}/{result['total']} 篇")
        if result.get("output_dir"):
            print(f"输出目录: {result['output_dir']}")
    elif args.daemon:
        run_scheduler(config_path=args.config, run_time=args.time)
    else:
        parser.print_help()
