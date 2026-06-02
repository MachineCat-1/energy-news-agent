import logging

import requests

import config

logger = logging.getLogger(__name__)


def send_wechat(run_date: str, fact_brief: str, analysis_report: str) -> None:
    """Send summary to WeChat Work webhook if configured."""
    if not config.WECHAT_WEBHOOK_URL:
        return
    summary = fact_brief[:500] if fact_brief else "无简报内容"
    content = (
        f"## 每日能源简报 · {run_date}\n\n"
        f"{summary}\n\n"
        f"---\nAI 分析报告已生成，请查看 Streamlit 页面。"
    )
    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    try:
        resp = requests.post(config.WECHAT_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("企业微信推送成功")
    except Exception as exc:
        logger.error("企业微信推送失败: %s", exc)
