import json
import logging

import config
from agents.llm_client import get_reasoner_client, invoke_json, load_prompt

logger = logging.getLogger(__name__)


def run_critic(analyzed_items: list[dict], news_items: list[dict]) -> dict:
    """Quality scoring with DeepSeek V4 Pro (thinking mode)."""
    system = load_prompt("critic", pass_score=str(config.CRITIC_PASS_SCORE))
    user = json.dumps(
        {"analyzed_items": analyzed_items, "original_news": news_items},
        ensure_ascii=False,
        indent=2,
    )

    client = get_reasoner_client()
    result = invoke_json(client, system, user)

    score = float(result.get("score", 0))
    passed = result.get("passed", score >= config.CRITIC_PASS_SCORE)
    feedback = result.get("feedback", "")

    logger.info("Critic 评分: %.1f, passed=%s", score, passed)
    return {"score": score, "feedback": feedback, "passed": passed}
