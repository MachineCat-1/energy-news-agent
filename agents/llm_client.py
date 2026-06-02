import json
import logging
import re
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import config

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str, **kwargs: str) -> str:
    """Load a prompt template from agents/prompts/ and format placeholders."""
    path = PROMPTS_DIR / f"{name}.txt"
    text = path.read_text(encoding="utf-8")
    if kwargs:
        text = text.format(**kwargs)
    return text


def _get_pro_client(model: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        temperature=temperature,
        extra_body={
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
        },
    )


def get_chat_client() -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        temperature=0.3,
    )


def get_reasoner_client() -> ChatOpenAI:
    """Critic agent client — defaults to deepseek-v4-pro with thinking mode."""
    return _get_pro_client(config.DEEPSEEK_CRITIC_MODEL, temperature=0.1)


def get_analysis_client() -> ChatOpenAI:
    """Analysis Writer client — defaults to deepseek-v4-pro with thinking mode."""
    return _get_pro_client(config.DEEPSEEK_ANALYSIS_MODEL, temperature=0.3)


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text


def invoke_text(client: ChatOpenAI, system: str, user: str) -> str:
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    response = client.invoke(messages)
    return response.content or ""


def invoke_json(client: ChatOpenAI, system: str, user: str) -> dict:
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    for attempt in range(2):
        try:
            response = client.invoke(messages)
            raw = _strip_json_fence(response.content or "")
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("JSON parse failed (attempt %d): %s", attempt + 1, exc)
            if attempt == 0:
                messages.append(
                    HumanMessage(content="请严格只输出合法 JSON，不要包含 markdown 代码块或额外说明。")
                )
            else:
                raise
    return {}
