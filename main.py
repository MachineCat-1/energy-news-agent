import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

import config
from agents.graph import run_pipeline

BASE_DIR = Path(__file__).resolve().parent


def setup_logging() -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = config.LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def start_streamlit() -> subprocess.Popen:
    app_path = BASE_DIR / "web" / "app.py"
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", "8501"],
        cwd=str(BASE_DIR),
    )


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    def job():
        logging.getLogger(__name__).info("定时任务触发 pipeline")
        run_pipeline()

    scheduler.add_job(
        job,
        "cron",
        hour=config.SCHEDULE_HOUR,
        minute=config.SCHEDULE_MINUTE,
        id="daily_energy_pipeline",
    )
    scheduler.start()
    logging.getLogger(__name__).info(
        "调度器已启动，每天 %02d:%02d 执行",
        config.SCHEDULE_HOUR,
        config.SCHEDULE_MINUTE,
    )
    return scheduler


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="中国能源新闻 Agent")
    parser.add_argument("--run-now", action="store_true", help="立即执行一次 pipeline")
    parser.add_argument("--web-only", action="store_true", help="仅启动 Streamlit")
    parser.add_argument(
        "--writers-only",
        action="store_true",
        help="跳过采集，用当日 SQLite 已有新闻重新生成报告",
    )
    args = parser.parse_args()

    if args.run_now:
        logging.getLogger(__name__).info("手动触发 pipeline")
        run_pipeline()
        return

    if args.writers_only:
        logging.getLogger(__name__).info("跳过采集，仅重新生成报告")
        run_pipeline(skip_collect=True)
        return

    if args.web_only:
        proc = start_streamlit()
        proc.wait()
        return

    scheduler = start_scheduler()
    proc = start_streamlit()
    try:
        proc.wait()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("收到退出信号")
    finally:
        scheduler.shutdown(wait=False)
        proc.terminate()


if __name__ == "__main__":
    main()
