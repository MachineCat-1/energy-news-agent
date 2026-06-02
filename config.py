import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# 显式加载项目根目录 .env，并覆盖系统环境变量中的旧值
load_dotenv(BASE_DIR / ".env", override=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
EIA_API_KEY = os.getenv("EIA_API_KEY", "")
WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL", "")

SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "7"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(BASE_DIR / "data" / "db" / "chroma"))
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "data" / "db" / "news.db"))
REPORTS_DIR = BASE_DIR / "data" / "reports"
LOGS_DIR = BASE_DIR / "data" / "logs"
KEYWORDS_FILE = BASE_DIR / "data" / "energy_keywords.txt"

SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
MAX_NEWS_PER_RUN = int(os.getenv("MAX_NEWS_PER_RUN", "50"))
CRITIC_RETRY_LIMIT = int(os.getenv("CRITIC_RETRY_LIMIT", "3"))
CRITIC_PASS_SCORE = float(os.getenv("CRITIC_PASS_SCORE", "7.0"))
DEEPSEEK_CRITIC_MODEL = os.getenv("DEEPSEEK_CRITIC_MODEL", "deepseek-v4-pro")
DEEPSEEK_ANALYSIS_MODEL = os.getenv("DEEPSEEK_ANALYSIS_MODEL", "deepseek-v4-pro")
BRIEF_FOOTER = os.getenv("BRIEF_FOOTER", "南京绿新能源研究院 竞争情报中心 精选敬赠")
BRIEF_TITLE_PREFIX = os.getenv("BRIEF_TITLE_PREFIX", "Econergy绿微报")
BRIEF_MAX_ITEMS = int(os.getenv("BRIEF_MAX_ITEMS", "15"))
BRIEF_ITEM_MIN_CHARS = int(os.getenv("BRIEF_ITEM_MIN_CHARS", "120"))
BRIEF_ITEM_MAX_CHARS = int(os.getenv("BRIEF_ITEM_MAX_CHARS", "320"))
# Comma-separated sources excluded from fact brief (default: EIA)
BRIEF_EXCLUDED_SOURCES = os.getenv("BRIEF_EXCLUDED_SOURCES", "EIA")
# China-focused defaults: EIA RSS / market API off unless explicitly enabled
ENABLE_EIA_RSS = os.getenv("ENABLE_EIA_RSS", "false").lower() in ("1", "true", "yes")
ENABLE_EIA_MARKET = os.getenv("ENABLE_EIA_MARKET", "false").lower() in ("1", "true", "yes")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Ensure data directories exist
for _dir in [REPORTS_DIR, LOGS_DIR, Path(CHROMA_DB_PATH).parent, Path(SQLITE_DB_PATH).parent]:
    _dir.mkdir(parents=True, exist_ok=True)
