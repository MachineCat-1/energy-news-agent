from datetime import datetime

import config
from output.brief_selection import select_brief_items


def format_market_table(market_data: list[dict]) -> str:
    """Format market data as Markdown table."""
    if not market_data:
        return "暂无行情数据"
    lines = ["| 指标 | 数值 | 单位 | 日期 | 涨跌幅 |", "|------|------|------|------|--------|"]
    for item in market_data:
        change = item.get("change_pct")
        change_str = f"{change:+.2f}%" if change is not None else "N/A"
        lines.append(
            f"| {item.get('metric', '')} | {item.get('value', '')} | "
            f"{item.get('unit', '')} | {item.get('date', '')} | {change_str} |"
        )
    return "\n".join(lines)


def report_header(title: str, run_date: str | None = None) -> str:
    date = run_date or datetime.now().strftime("%Y-%m-%d")
    return f"# {title} · {date}\n"


def _unique_sources(items: list[dict]) -> str:
    sources = []
    for item in items:
        s = item.get("source", "")
        if s and s not in sources:
            sources.append(s)
    return "、".join(sources) if sources else "多源"


def _item_body(item: dict) -> str:
    """Build brief paragraph from summary + content when summary is too short."""
    summary = (item.get("summary") or "").replace("\n", " ").strip()
    content = (item.get("content") or item.get("title") or "").replace("\n", " ").strip()
    max_chars = config.BRIEF_ITEM_MAX_CHARS

    if len(summary) >= config.BRIEF_ITEM_MIN_CHARS:
        body = summary
    elif summary and content:
        room = max_chars - len(summary) - 1
        body = f"{summary}。{content[:room]}" if room > 40 else summary or content
    else:
        body = summary or content

    if len(body) > max_chars:
        body = body[: max_chars - 3] + "..."
    return body


def build_fact_brief_lvwbao(
    run_date: str,
    analyzed_items: list[dict],
    market_data: list[dict] | None = None,
    max_items: int | None = None,
) -> str:
    """Deterministic 绿微报-style brief from analyzed news items."""
    max_items = max_items or config.BRIEF_MAX_ITEMS
    items = select_brief_items(analyzed_items, max_items=max_items)

    date_compact = run_date.replace("-", "")
    sources = _unique_sources(items)
    lines = [
        f"# {date_compact}{config.BRIEF_TITLE_PREFIX}",
        f"> 本简报仅含可溯源事实，共 {len(items)} 条，来源 {sources}",
        "",
        "## 市场行情",
        format_market_table(market_data or []),
        "",
        "## 今日要闻",
        "",
    ]

    for idx, item in enumerate(items, 1):
        summary = _item_body(item)
        source = item.get("source", "未知")
        url = item.get("url", "")
        link = f"[查看原文]({url})" if url else ""
        lines.append(f"{idx}、{summary}【来源：{source}】{link}")
        lines.append("")

    lines.append(config.BRIEF_FOOTER)
    return "\n".join(lines).strip() + "\n"


def is_brief_empty(brief: str) -> bool:
    if not brief or len(brief) < 100:
        return True
    if "共 0 条" in brief:
        return True
    if "## 今日要闻" in brief:
        section = brief.split("## 今日要闻", 1)[-1].strip()
        if not section or section.startswith("##") or len(section) < 20:
            return True
    return False
