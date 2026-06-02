import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

import config
from memory import news_store

st.set_page_config(page_title="中国能源新闻 Agent", layout="wide")
st.title("中国能源新闻 Agent")


def list_report_dates() -> list[str]:
    if not config.REPORTS_DIR.exists():
        return []
    dates = sorted(
        [d.name for d in config.REPORTS_DIR.iterdir() if d.is_dir()],
        reverse=True,
    )
    db_dates = news_store.list_run_dates()
    merged = list(dict.fromkeys(dates + db_dates))
    return merged


def load_report_file(date: str, filename: str) -> str:
    path = config.REPORTS_DIR / date / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_market_data(date: str) -> list[dict]:
    path = config.REPORTS_DIR / date / "market_data.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []


def render_confidence_bars(report: str) -> None:
    sections = re.split(r"(?=## 分析)", report)
    for section in sections:
        if not section.strip():
            continue
        match = re.search(r"【置信度：(\d+)%】", section)
        if match:
            confidence = int(match.group(1))
            title_match = re.search(r"## (分析[^\n]*)", section)
            title = title_match.group(1) if title_match else "分析"
            st.markdown(section.split("【置信度")[0])
            st.progress(confidence / 100, text=f"{title} - 置信度 {confidence}%")
        elif section.strip().startswith("#"):
            st.markdown(section)


dates = list_report_dates()
with st.sidebar:
    st.header("报告选择")
    selected_date = st.selectbox("日期", dates if dates else ["暂无报告"])
    st.caption("选择日期查看对应的事实简报与 AI 分析")

if not dates or selected_date == "暂无报告":
    st.info("暂无报告，请运行 `python main.py --run-now` 生成首份报告。")
    st.stop()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("事实简报")
    market_data = load_market_data(selected_date)
    if market_data:
        st.markdown("#### 市场行情")
        cols = st.columns(len(market_data))
        for i, item in enumerate(market_data):
            with cols[i]:
                change = item.get("change_pct")
                delta = f"{change:+.2f}%" if change is not None else None
                st.metric(
                    label=item.get("metric", ""),
                    value=f"{item.get('value', '')} {item.get('unit', '')}",
                    delta=delta,
                )
    fact_brief = load_report_file(selected_date, "fact_brief.md")
    if fact_brief:
        st.markdown(fact_brief)
    else:
        st.warning("该日期暂无事实简报")

with col_right:
    st.subheader("AI 分析报告")
    analysis_report = load_report_file(selected_date, "analysis_report.md")
    if analysis_report:
        render_confidence_bars(analysis_report)
    else:
        st.warning("该日期暂无 AI 分析报告")

st.divider()
st.subheader("运行日志")
run_meta = news_store.get_run_meta(selected_date)
if run_meta:
    log_cols = st.columns(4)
    log_cols[0].metric("采集条数", run_meta["collected"])
    log_cols[1].metric("去重后条数", run_meta["deduped"])
    log_cols[2].metric("Critic 评分", f"{run_meta['critic_score']:.1f}")
    log_cols[3].metric("重试次数", run_meta["retry_count"])
    st.caption(f"状态: {run_meta['status']}")
else:
    st.caption("暂无运行元数据")
