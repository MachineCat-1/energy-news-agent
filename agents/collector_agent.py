import logging
from datetime import datetime

from collector import api_fetcher, deduplicator, rss_fetcher, web_scraper
from memory import news_store

logger = logging.getLogger(__name__)


def run_collection(run_date: str | None = None) -> dict:
    """Orchestrate all collectors, deduplicate, and persist raw news."""
    run_date = run_date or datetime.now().strftime("%Y-%m-%d")
    logger.info("开始采集，run_date=%s", run_date)

    raw_items: list[dict] = []
    raw_items.extend(rss_fetcher.fetch_all_rss())
    raw_items.extend(web_scraper.fetch_all_web())
    collected_count = len(raw_items)

    market_data = api_fetcher.fetch_market_data()
    deduped = deduplicator.deduplicate(raw_items)
    deduped_count = len(deduped)

    news_store.save_news(deduped, run_date)
    news_store.save_run_meta(
        run_date=run_date,
        collected=collected_count,
        deduped=deduped_count,
        critic_score=0.0,
        retry_count=0,
        status="collecting",
    )

    logger.info("采集完成: 原始 %d 条, 去重后 %d 条", collected_count, deduped_count)
    return {
        "news_items": deduped,
        "market_data": market_data,
        "run_date": run_date,
        "collected_count": collected_count,
        "deduped_count": deduped_count,
    }
