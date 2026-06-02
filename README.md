# 中国能源新闻 Agent

每日自动采集中国能源新闻与 EIA 官方数据，经 LangGraph 多 Agent 流水线处理后，生成**事实简报**（可溯源）与 **AI 分析报告**（含置信度标注）。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 EIA_API_KEY

# 3. 立即运行一次（测试）
python main.py --run-now

# 4. 启动定时调度 + Web 界面
python main.py

# 或仅启动 Web
python main.py --web-only
# 也可: streamlit run web/app.py
```

浏览器访问 http://localhost:8501 查看报告。

## 架构说明

| Agent | 职责 |
|-------|------|
| **Collector** | 协调 RSS、网页、API 采集，语义去重后存入 SQLite |
| **Analyst** | 分类打标、实体提取、摘要生成，召回 skill memory 作为参考 |
| **Critic** | 用 DeepSeek-R1 评分质检，未通过则打回 Analyst 重试（最多 3 次） |
| **Fact Writer** | 仅输出可溯源事实，每条绑定来源 |
| **Analysis Writer** | 仅基于事实简报推断，标注置信度与 AI 免责声明 |

流水线：`collector → analyst → critic → [retry analyst | fact_writer + analysis_writer]`

## 数据源

| 来源 | 抓取方式 |
|------|----------|
| 财联社 | RSS (`feedparser`) |
| 澎湃新闻-能源 | 列表页 HTML 解析 |
| EIA News | RSS |
| 界面新闻-能源 | 网页爬取 |
| 国家能源局 | 公告页爬取 |
| EIA Open Data | REST API（WTI 原油、Henry Hub 天然气） |

## 注意事项

- **DeepSeek API**：在 [platform.deepseek.com](https://platform.deepseek.com) 申请 API Key
- **EIA API**：在 [eia.gov/opendata/register.php](https://www.eia.gov/opendata/register.php) 免费申请
- **首次运行**：会下载 `shibing624/text2vec-base-chinese` 模型（约数百 MB），用于语义去重
- **抓取频率**：网页爬虫源间间隔 2 秒，请勿频繁手动触发
- **企业微信推送**：在 `.env` 中配置 `WECHAT_WEBHOOK_URL` 后自动推送简报摘要

## 目录结构

```
├── main.py              # 入口：调度 + Streamlit
├── config.py            # 配置
├── collector/           # 数据采集
├── agents/              # LangGraph 多 Agent
├── memory/              # SQLite + ChromaDB
├── output/              # 格式化与通知
├── web/app.py           # Streamlit 展示
└── data/
    ├── reports/         # 每日报告
    ├── logs/            # 运行日志
    └── db/              # 数据库
```
