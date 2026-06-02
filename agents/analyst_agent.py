import json
import logging

import config
from agents.llm_client import get_chat_client, invoke_json, load_prompt
from memory import skill_memory

logger = logging.getLogger(__name__)


def run_analyst(news_items: list[dict], run_date: str, critic_feedback: str = "") -> dict:
    """Analyze news items with LLM; recall skill memory for few-shot."""
    skills = skill_memory.recall_similar_skills(run_date, top_k=3)
    skills_text = ""
    if skills:
        skills_text = "\n\n历史高分策略参考:\n" + "\n---\n".join(s["strategy"] for s in skills)

    system = load_prompt("analyst", date=run_date, min_chars=str(config.BRIEF_ITEM_MIN_CHARS), max_chars=str(min(config.BRIEF_ITEM_MAX_CHARS, 220)))
    user_payload = {
        "news_items": news_items,
        "critic_feedback": critic_feedback,
        "skill_references": skills_text,
    }
    user = json.dumps(user_payload, ensure_ascii=False, indent=2)

    client = get_chat_client()
    result = invoke_json(client, system, user)

    analyzed_items = []
    item_map = {item["id"]: item for item in news_items}
    for idx, analyzed in enumerate(result.get("items", [])):
        base = item_map.get(analyzed.get("id"), {})
        if not base.get("title") and idx < len(news_items):
            base = news_items[idx]
        merged = {**base, **analyzed}
        if merged.get("title"):
            analyzed_items.append(merged)

    if not analyzed_items and news_items:
        logger.warning("Analyst 返回空结果，使用原始新闻")
        analyzed_items = news_items

    return {
        "analyzed_items": analyzed_items,
        "strategy_note": result.get("strategy_note", ""),
    }
