import logging

from agents.llm_client import get_analysis_client, invoke_text, load_prompt

logger = logging.getLogger(__name__)


def run_analysis_writer(fact_brief: str, run_date: str) -> str:
    """Generate AI analysis report based ONLY on fact brief."""
    system = load_prompt("analysis_writer", date=run_date)
    user = f"已核实的事实简报如下：\n\n{fact_brief}"
    client = get_analysis_client()
    report = invoke_text(client, system, user)
    logger.info("AI 分析报告生成完成，长度 %d", len(report))
    return report
