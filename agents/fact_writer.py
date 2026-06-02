import json
import logging

import config
from agents.llm_client import get_chat_client, invoke_text, load_prompt
from output.brief_selection import select_brief_items
from output.formatter import build_fact_brief_lvwbao, is_brief_empty

logger = logging.getLogger(__name__)

_BRIEF_PAYLOAD_KEYS = (
    "id",
    "title",
    "summary",
    "content",
    "entities",
    "source",
    "url",
    "category",
)


def _brief_payload_item(item: dict) -> dict:
    """Richer context for Fact Writer — include content excerpt for detail."""
    payload = {k: item.get(k) for k in _BRIEF_PAYLOAD_KEYS if item.get(k) is not None}
    content = (item.get("content") or "").replace("\n", " ").strip()
    if content:
        payload["content_excerpt"] = content[:800]
    payload.pop("content", None)
    return payload


def run_fact_writer(analyzed_items: list[dict], market_data: list[dict], run_date: str) -> str:
    """Generate fact-only brief in 绿微报 Markdown format."""
    date_compact = run_date.replace("-", "")
    brief_items = select_brief_items(analyzed_items)
    system = load_prompt(
        "fact_writer",
        date=run_date,
        date_compact=date_compact,
        footer=config.BRIEF_FOOTER,
        max_items=str(config.BRIEF_MAX_ITEMS),
        min_chars=str(config.BRIEF_ITEM_MIN_CHARS),
        max_chars=str(config.BRIEF_ITEM_MAX_CHARS),
    )
    user = json.dumps(
        {
            "analyzed_items": [_brief_payload_item(item) for item in brief_items],
            "market_data": market_data,
        },
        ensure_ascii=False,
        indent=2,
    )
    client = get_chat_client()
    brief = invoke_text(client, system, user)
    logger.info(
        "事实简报生成完成，长度 %d（候选 %d 条，国内优先）",
        len(brief),
        len(brief_items),
    )

    if is_brief_empty(brief):
        logger.warning("LLM 简报为空或无效，使用 formatter 兜底生成")
        brief = build_fact_brief_lvwbao(run_date, analyzed_items, market_data)

    return brief
