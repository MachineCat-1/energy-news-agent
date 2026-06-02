import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2"


def _calc_change_pct(values: list[dict]) -> float | None:
    if len(values) < 2:
        return None
    latest = values[0].get("value")
    prev = values[1].get("value")
    if latest is None or prev is None or prev == 0:
        return None
    return round((latest - prev) / prev * 100, 2)


def _fetch_eia_series(route: str, params: dict) -> list[dict]:
    if not config.EIA_API_KEY:
        logger.warning("EIA_API_KEY 未配置，跳过行情数据抓取")
        return []
    url = f"{EIA_BASE}/{route}"
    params = {**params, "api_key": config.EIA_API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", {}).get("data", [])
    except Exception as exc:
        logger.error("EIA API 请求失败 %s: %s", route, exc)
        return []


def fetch_wti_prices(days: int = 7) -> list[dict]:
    """WTI 原油现货价格."""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days + 3)).strftime("%Y-%m-%d")
    rows = _fetch_eia_series(
        "petroleum/pri/spt/data",
        {
            "frequency": "daily",
            "data[0]": "value",
            "facets[series][]": "RWTC",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": 0,
            "length": days + 1,
            "start": start,
            "end": end,
        },
    )
    parsed = [{"date": r.get("period"), "value": float(r.get("value", 0))} for r in rows if r.get("value")]
    if not parsed:
        return []
    change = _calc_change_pct(parsed)
    latest = parsed[0]
    return [
        {
            "metric": "WTI原油",
            "value": latest["value"],
            "unit": "USD/桶",
            "date": latest["date"],
            "change_pct": change,
        }
    ]


def fetch_henry_hub_prices(days: int = 7) -> list[dict]:
    """Henry Hub 天然气价格."""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days + 3)).strftime("%Y-%m-%d")
    rows = _fetch_eia_series(
        "natural-gas/pri/sum/data",
        {
            "frequency": "daily",
            "data[0]": "value",
            "facets[series][]": "RNGWHHD",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": 0,
            "length": days + 1,
            "start": start,
            "end": end,
        },
    )
    parsed = [{"date": r.get("period"), "value": float(r.get("value", 0))} for r in rows if r.get("value")]
    if not parsed:
        return []
    change = _calc_change_pct(parsed)
    latest = parsed[0]
    return [
        {
            "metric": "Henry Hub天然气",
            "value": latest["value"],
            "unit": "USD/MMBtu",
            "date": latest["date"],
            "change_pct": change,
        }
    ]


def fetch_market_data() -> list[dict]:
    """Fetch all market metrics."""
    if not config.ENABLE_EIA_MARKET:
        logger.info("EIA 行情已关闭（ENABLE_EIA_MARKET=false）")
        return []

    cache_dir = config.REPORTS_DIR / datetime.now().strftime("%Y-%m-%d")
    cache_file = cache_dir / "market_data.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    data: list[dict] = []
    data.extend(fetch_wti_prices())
    data.extend(fetch_henry_hub_prices())
    logger.info("行情数据采集完成，共 %d 条", len(data))

    if data:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
