"""Select news items for fact brief — domestic sources first, exclude configured sources."""

import config

# Lower number = higher priority in brief
DOMESTIC_SOURCE_PRIORITY: dict[str, int] = {
    "国家能源局": 0,
    "财联社": 1,
    "界面新闻": 2,
    "澎湃": 3,
}


def _excluded_sources() -> set[str]:
    raw = config.BRIEF_EXCLUDED_SOURCES.strip()
    if not raw:
        return set()
    return {s.strip() for s in raw.split(",") if s.strip()}


def select_brief_items(
    analyzed_items: list[dict],
    max_items: int | None = None,
) -> list[dict]:
    """Pick items for 绿微报: drop excluded sources, prefer domestic, newest first."""
    max_items = max_items or config.BRIEF_MAX_ITEMS
    excluded = _excluded_sources()

    candidates = [
        item
        for item in analyzed_items
        if item.get("title") and len(item.get("title", "")) >= 8 and item.get("source") not in excluded
    ]

    candidates.sort(key=lambda x: x.get("published_at", "") or "", reverse=True)
    candidates.sort(key=lambda x: DOMESTIC_SOURCE_PRIORITY.get(x.get("source", ""), 100))

    return candidates[:max_items]
