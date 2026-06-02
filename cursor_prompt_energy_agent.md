# 中国能源新闻 Agent —— Cursor 项目生成提示词

## 项目概述

构建一个每日自动运行的能源新闻 Agent，面向中国市场，核心功能是每天早上自动抓取中文能源新闻和官方数据，经过 multi-agent 处理后，分别生成两份产出物：
1. **事实简报**：仅含可溯源的事实，每条绑定原文链接
2. **AI 分析报告**：基于事实推断，标注置信度，明确标明"AI 观点"

---

## 技术栈

- **语言**：Python 3.11+
- **Agent 框架**：LangGraph（`langgraph`）
- **LLM**：DeepSeek API（`openai` 兼容接口）
  - 常规 agent 用 `deepseek-chat`（DeepSeek-V3）
  - Critic agent 用 `deepseek-reasoner`（DeepSeek-R1）
- **数据抓取**：`feedparser`、`requests`、`beautifulsoup4`、`httpx`
- **中文 NLP**：`jieba`、`sentence-transformers`（用 `shibing624/text2vec-base-chinese`）
- **向量库**：`chromadb`（本地）
- **数据库**：`sqlite3`（标准库）
- **调度**：`apscheduler`
- **前端展示**：`streamlit`
- **环境变量**：`python-dotenv`

---

## 目录结构

请按如下结构创建项目：

```
energy-agent/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── main.py                    # 入口，启动调度器
├── config.py                  # 全局配置（从 .env 读取）
│
├── collector/
│   ├── __init__.py
│   ├── rss_fetcher.py         # RSS 抓取（财联社、澎湃、EIA）
│   ├── web_scraper.py         # 网页爬取（界面新闻、国家能源局）
│   ├── api_fetcher.py         # 结构化 API（EIA Open Data、国家统计局）
│   └── deduplicator.py        # 语义去重（向量余弦相似度）
│
├── agents/
│   ├── __init__.py
│   ├── graph.py               # LangGraph 主图定义
│   ├── collector_agent.py     # 协调采集，触发 collector/ 各模块
│   ├── analyst_agent.py       # 分类、打标、摘要、召回 skill memory
│   ├── critic_agent.py        # 质量评分、推断词检测、打回重试
│   ├── fact_writer.py         # 事实简报生成
│   └── analysis_writer.py     # AI 分析报告生成（含置信度）
│
├── memory/
│   ├── __init__.py
│   ├── skill_memory.py        # 高分策略存取（ChromaDB）
│   └── news_store.py          # 原始新闻存取（SQLite）
│
├── output/
│   ├── __init__.py
│   ├── formatter.py           # Markdown 格式化
│   └── notifier.py            # 推送（企业微信 webhook / 邮件，可选）
│
├── web/
│   └── app.py                 # Streamlit 展示页面
│
└── data/
    ├── energy_keywords.txt    # 能源关键词词表
    └── db/                    # SQLite 和 ChromaDB 文件存放
```

---

## 各模块详细要求

### config.py

从 `.env` 读取以下配置：

```python
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
EIA_API_KEY = ""          # EIA Open Data 免费申请
WECHAT_WEBHOOK_URL = ""   # 企业微信 webhook，可选
SCHEDULE_HOUR = 7         # 每天几点触发
SCHEDULE_MINUTE = 0
CHROMA_DB_PATH = "./data/db/chroma"
SQLITE_DB_PATH = "./data/db/news.db"
SIMILARITY_THRESHOLD = 0.85   # 去重阈值
MAX_NEWS_PER_RUN = 50
CRITIC_RETRY_LIMIT = 3
CRITIC_PASS_SCORE = 7.0       # Critic 评分 >= 7 才通过
```

---

### collector/rss_fetcher.py

用 `feedparser` 抓取以下 RSS 源，返回标准化的新闻列表：

| 来源 | RSS 地址 |
|------|---------|
| 财联社-能源 | `https://www.cls.cn/rss` |
| 澎湃新闻-能源 | `https://www.thepaper.cn/channel_25950` （用 requests 抓列表页） |
| EIA News | `https://www.eia.gov/rss/news.xml` |

每条新闻标准化为：
```python
{
  "id": str,           # md5(url)
  "title": str,
  "content": str,      # 正文摘要，尽量抓全文，失败则用 summary
  "url": str,
  "source": str,       # "财联社" / "澎湃" / "EIA"
  "published_at": str, # ISO 8601
  "category": str,     # 初始为 "unknown"，由 analyst 填写
  "tags": list[str],
}
```

---

### collector/web_scraper.py

爬取以下页面，注意加 `User-Agent` header，请求间隔 2 秒：

- **界面新闻能源频道**：`https://www.jiemian.com/lists/2.html`，抓标题 + 链接 + 摘要
- **国家能源局新闻**：`http://www.nea.gov.cn/gjnyj/index.htm`，抓公告标题 + 链接

用 `BeautifulSoup` 解析，正文用 `requests` 二次请求获取，失败则保留摘要。

---

### collector/api_fetcher.py

对接 EIA Open Data API：

- 端点：`https://api.eia.gov/v2/petroleum/pri/spt/data/`
- 获取 WTI 原油现货价格（最近 7 天）
- 获取 Henry Hub 天然气价格

返回格式：
```python
{
  "metric": "WTI原油",
  "value": 78.4,
  "unit": "USD/桶",
  "date": "2025-05-22",
  "change_pct": 1.2   # 与前一日对比涨跌幅
}
```

---

### collector/deduplicator.py

使用 `sentence-transformers` 加载 `shibing624/text2vec-base-chinese` 模型，对新闻标题做向量化，计算余弦相似度，过滤相似度 > `SIMILARITY_THRESHOLD` 的重复条目，保留最早发布的那条。

---

### agents/graph.py

用 LangGraph 定义 StateGraph，节点顺序：

```
collector_node → analyst_node → critic_node → [fact_writer_node, analysis_writer_node]
```

State 定义：
```python
class AgentState(TypedDict):
    news_items: list[dict]         # 原始新闻
    analyzed_items: list[dict]     # analyst 处理后
    critic_score: float            # critic 评分
    critic_feedback: str           # critic 反馈
    retry_count: int               # 已重试次数
    fact_brief: str                # 事实简报 Markdown
    analysis_report: str           # 分析报告 Markdown
    market_data: list[dict]        # 行情数据
```

critic_node 之后加条件边：
- 评分 < `CRITIC_PASS_SCORE` 且 `retry_count` < `CRITIC_RETRY_LIMIT` → 回到 analyst_node
- 否则 → 并行执行 fact_writer_node 和 analysis_writer_node

---

### agents/analyst_agent.py

使用 `deepseek-chat` 模型。

System prompt 核心要求：
- 对每条新闻打分类标签（`oil`/`gas`/`renewables`/`policy`/`market`）
- 提取关键实体（公司名、地区、数值）
- 用中文生成 80 字以内摘要
- 在生成前，先从 skill_memory 召回近 3 条相似日期的高分分析策略，作为 few-shot 参考
- 输出 JSON 格式

---

### agents/critic_agent.py

使用 `deepseek-reasoner` 模型（DeepSeek-R1）。

评分维度（满分 10 分）：
1. **完整性**：重要新闻是否覆盖（3分）
2. **准确性**：摘要是否与原文一致（4分）
3. **推断词检测**：摘要中有无"预计"、"可能"、"分析认为"、"或将"等词（-2分/个）

返回：
```python
{
  "score": float,
  "feedback": str,    # 具体指出问题
  "passed": bool
}
```

---

### agents/fact_writer.py

使用 `deepseek-chat` 模型。

System prompt 硬规则（必须写进 prompt）：
```
你是一名财经新闻编辑，只能陈述事实。
规则：
1. 每一句话必须对应一个来源，在句末用【来源：XXX】标注
2. 禁止使用的词：预计、可能、或将、分析认为、预期、有望、料将、估计
3. 发现无法确认来源的内容，直接删除，不得保留
4. 输出格式为 Markdown
```

输出结构：
```markdown
# 每日能源简报 · {date}
> 本简报仅含可溯源事实，共 {n} 条，来源 {sources}

## 市场行情
...（含涨跌幅，数据来自 EIA API）

## 今日要闻
### 1. {标题}
{摘要}【来源：{source}】[查看原文]({url})

...
```

---

### agents/analysis_writer.py

使用 `deepseek-chat` 模型。

**重要**：此 agent 只接收 `fact_brief` 作为输入，不接触原始新闻，防止分析混入未核实内容。

System prompt 核心：
```
你是能源行业分析师。基于以下已核实的事实简报进行推断分析。
规则：
1. 每条分析必须引用事实简报中的具体事实作为依据
2. 每条分析后附置信度评分（0-100），格式：【置信度：XX%】
3. 在报告开头用醒目方式标注"以下为 AI 推断，不构成投资建议"
4. 分析条数：3-5 条
```

---

### memory/skill_memory.py

用 ChromaDB 存储高分分析经验：

```python
# 存入（每次 critic 评分 >= 8 时触发）
def save_skill(date: str, analyst_strategy: str, score: float): ...

# 召回（analyst 启动时调用）
def recall_similar_skills(current_date: str, top_k: int = 3) -> list[dict]: ...
```

---

### web/app.py

用 Streamlit 构建展示页面，包含：

1. **侧边栏**：日期选择器，选择查看哪天的报告
2. **主区域左栏**：事实简报（带行情数据卡片：WTI、天然气、欧洲电价）
3. **主区域右栏**：AI 分析报告（每条分析下有置信度进度条）
4. **底部**：本次运行 log（采集条数、去重后条数、Critic 评分、重试次数）

---

### main.py

```python
# 用 APScheduler 每天 SCHEDULE_HOUR:SCHEDULE_MINUTE 触发一次完整 pipeline
# 同时启动 Streamlit web 服务
# 支持命令行参数 --run-now 立即触发一次（用于测试）
```

---

## requirements.txt 需包含

```
langgraph>=0.2
langchain-openai>=0.1
openai>=1.0
feedparser
requests
beautifulsoup4
httpx
jieba
sentence-transformers
chromadb
apscheduler
streamlit
python-dotenv
```

---

## .env.example

```
DEEPSEEK_API_KEY=your_key_here
EIA_API_KEY=your_key_here
WECHAT_WEBHOOK_URL=
SCHEDULE_HOUR=7
SCHEDULE_MINUTE=0
```

---

## README.md 需包含

1. 项目简介（一段话）
2. 快速开始（clone → pip install → 配置 .env → python main.py --run-now）
3. 架构说明（简述 4 个 agent 的分工）
4. 数据源说明（列出所有来源及抓取方式）
5. 注意事项（EIA API 申请链接、requests 抓取频率限制）

---

## 额外要求

- 所有 LLM 调用统一封装在 `agents/llm_client.py` 中，方便后续换模型
- 所有 agent 的 system prompt 统一存放在 `agents/prompts/` 目录下的 `.txt` 文件，不要硬编码在 Python 文件里
- 每次运行结果（简报 + 分析）保存到 `data/reports/{date}/` 目录下的 `.md` 文件
- 关键步骤加 `logging`，日志写到 `data/logs/` 目录
- collector 的各抓取函数加 `try/except`，单个数据源失败不影响整体运行
