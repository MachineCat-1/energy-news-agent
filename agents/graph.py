import json
import logging
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

import config
from agents import (
    analysis_writer,
    analyst_agent,
    collector_agent,
    critic_agent,
    fact_writer,
)
from memory import news_store, skill_memory
from output import notifier

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    news_items: list[dict]
    analyzed_items: list[dict]
    critic_score: float
    critic_feedback: str
    retry_count: int
    fact_brief: str
    analysis_report: str
    market_data: list[dict]
    run_date: str
    collected_count: int
    deduped_count: int
    strategy_note: str
    passed: bool


def collector_node(state: AgentState) -> AgentState:
    run_date = state.get("run_date") or ""
    if state.get("news_items"):
        return state
    result = collector_agent.run_collection(run_date or None)
    return {
        **state,
        "news_items": result["news_items"],
        "market_data": result["market_data"],
        "run_date": result["run_date"],
        "collected_count": result["collected_count"],
        "deduped_count": result["deduped_count"],
        "retry_count": state.get("retry_count", 0),
    }


def analyst_node(state: AgentState) -> AgentState:
    result = analyst_agent.run_analyst(
        state["news_items"],
        state["run_date"],
        critic_feedback=state.get("critic_feedback", ""),
    )
    return {
        **state,
        "analyzed_items": result["analyzed_items"],
        "strategy_note": result.get("strategy_note", ""),
    }


def critic_node(state: AgentState) -> AgentState:
    result = critic_agent.run_critic(state["analyzed_items"], state["news_items"])
    retry = state.get("retry_count", 0)
    if not result["passed"]:
        retry += 1
    return {
        **state,
        "critic_score": result["score"],
        "critic_feedback": result["feedback"],
        "passed": result["passed"],
        "retry_count": retry,
    }


def fact_writer_node(state: AgentState) -> AgentState:
    brief = fact_writer.run_fact_writer(
        state["analyzed_items"],
        state.get("market_data", []),
        state["run_date"],
    )
    return {**state, "fact_brief": brief}


def analysis_writer_node(state: AgentState) -> AgentState:
    fact_brief = state.get("fact_brief", "")
    if not fact_brief:
        fact_brief = fact_writer.run_fact_writer(
            state["analyzed_items"],
            state.get("market_data", []),
            state["run_date"],
        )
    report = analysis_writer.run_analysis_writer(fact_brief, state["run_date"])
    return {**state, "fact_brief": fact_brief, "analysis_report": report}


def route_after_critic(state: AgentState) -> Literal["analyst_node", "writers"]:
    score = state.get("critic_score", 0)
    retry = state.get("retry_count", 0)
    if score < config.CRITIC_PASS_SCORE and retry < config.CRITIC_RETRY_LIMIT:
        logger.info("Critic 未通过 (%.1f)，重试 analyst，第 %d 次", score, retry)
        return "analyst_node"
    return "writers"


def writers_node(state: AgentState) -> AgentState:
    """Sequential writers: fact first, then analysis (analysis only reads fact_brief)."""
    state = fact_writer_node(state)
    state = analysis_writer_node(state)
    return state


def _save_outputs(state: AgentState) -> None:
    run_date = state["run_date"]
    report_dir = config.REPORTS_DIR / run_date
    report_dir.mkdir(parents=True, exist_ok=True)

    (report_dir / "fact_brief.md").write_text(state.get("fact_brief", ""), encoding="utf-8")
    (report_dir / "analysis_report.md").write_text(state.get("analysis_report", ""), encoding="utf-8")

    market_data = state.get("market_data", [])
    if market_data:
        (report_dir / "market_data.json").write_text(
            json.dumps(market_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    news_store.save_run_meta(
        run_date=run_date,
        collected=state.get("collected_count", 0),
        deduped=state.get("deduped_count", 0),
        critic_score=state.get("critic_score", 0),
        retry_count=state.get("retry_count", 0),
        status="completed",
    )

    score = state.get("critic_score", 0)
    if score >= 8 and state.get("strategy_note"):
        skill_memory.save_skill(run_date, state["strategy_note"], score)

    notifier.send_wechat(run_date, state.get("fact_brief", ""), state.get("analysis_report", ""))
    logger.info("报告已保存到 %s", report_dir)


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("collector_node", collector_node)
    graph.add_node("analyst_node", analyst_node)
    graph.add_node("critic_node", critic_node)
    graph.add_node("writers_node", writers_node)

    graph.add_edge(START, "collector_node")
    graph.add_edge("collector_node", "analyst_node")
    graph.add_edge("analyst_node", "critic_node")
    graph.add_conditional_edges(
        "critic_node",
        route_after_critic,
        {"analyst_node": "analyst_node", "writers": "writers_node"},
    )
    graph.add_edge("writers_node", END)

    return graph.compile()


def run_pipeline(run_date: str | None = None, skip_collect: bool = False) -> AgentState:
    from datetime import datetime

    run_date = run_date or datetime.now().strftime("%Y-%m-%d")
    app = build_graph()
    initial: AgentState = {"run_date": run_date, "retry_count": 0}
    if skip_collect:
        from memory import news_store

        news_items = news_store.get_news_by_date(run_date)
        if not news_items:
            raise RuntimeError(f"未找到 {run_date} 的已采集新闻，请先运行完整 pipeline")
        initial["news_items"] = news_items
        initial["collected_count"] = len(news_items)
        initial["deduped_count"] = len(news_items)
        initial["market_data"] = []
    final_state = app.invoke(initial)
    _save_outputs(final_state)
    return final_state
