import hashlib
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import jieba
import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

KEYWORDS: set[str] = set()

CLS_TELEGRAPH_URL = "https://www.cls.cn/telegraph"
CLS_MAX_ARTICLES = 25
EIA_RSS_URL = "https://www.eia.gov/rss/todayinenergy.xml"
THEPAPER_ENERGY_URL = "https://www.thepaper.cn/channel_25950"


def _load_keywords() -> set[str]:
    global KEYWORDS
    if KEYWORDS:
        return KEYWORDS
    if config.KEYWORDS_FILE.exists():
        KEYWORDS = {
            line.strip()
            for line in config.KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
    return KEYWORDS


def _is_energy_related(title: str, content: str) -> bool:
    keywords = _load_keywords()
    if not keywords:
        return True
    text = f"{title} {content}".lower()
    words = set(jieba.cut(text))
    for kw in keywords:
        if kw.lower() in text or kw in words:
            return True
    return False


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _fetch_url(url: str, timeout: int = 15) -> str | None:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except Exception as exc:
        logger.warning("页面请求失败 %s: %s", url, exc)
        return None


def _parse_feed(url: str):
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        return feedparser.parse(resp.content)
    except Exception as exc:
        logger.error("RSS 请求失败 %s: %s", url, exc)
        return feedparser.parse("")


def _extract_link_title(link) -> str:
    title = link.get_text(" ", strip=True)
    if title and len(title) >= 5:
        return title
    img = link.find("img")
    if img and img.get("alt"):
        return img["alt"].strip()
    return ""


def _parse_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except (TypeError, ValueError):
                pass
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw).isoformat()
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc).isoformat()


def _normalize_entry(
    title: str,
    content: str,
    url: str,
    source: str,
    published_at: str | None = None,
    skip_keyword_filter: bool = False,
) -> dict | None:
    title = (title or "").strip()
    url = (url or "").strip()
    content = (content or title).strip()
    if not title or not url:
        return None
    if not skip_keyword_filter and not _is_energy_related(title, content):
        return None
    return {
        "id": _make_id(url),
        "title": title,
        "content": content,
        "url": url,
        "source": source,
        "published_at": published_at or datetime.now(timezone.utc).isoformat(),
        "category": "unknown",
        "tags": [],
    }


def _fetch_cls_article_meta(article_id: str) -> tuple[str, str] | None:
    share_url = (
        f"https://api3.cls.cn/share/article/{article_id}"
        f"?os=web&sv=8.4.6&app=CailianpressWeb"
    )
    html = _fetch_url(share_url, timeout=10)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for tag_name, attrs in (
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "keywords"}),
        ("meta", {"name": "description"}),
    ):
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get("content"):
            title = tag["content"].strip()
            if title and title not in {"电报详情"}:
                return title, f"https://www.cls.cn/detail/{article_id}"
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        if title and title not in {"电报详情"}:
            return title, f"https://www.cls.cn/detail/{article_id}"
    return None


def _collect_cls_article_ids(html: str) -> list[str]:
    article_ids: list[str] = []
    for pattern in (r"share/article/(\d+)", r"/detail/(\d+)"):
        for match in re.finditer(pattern, html):
            aid = match.group(1)
            if aid not in article_ids:
                article_ids.append(aid)
    return article_ids[:CLS_MAX_ARTICLES]


def fetch_cls_rss() -> list[dict]:
    """财联社电报 - 原 RSS 已 404，改从 telegraph 页提取文章 ID 并拉取标题."""
    items: list[dict] = []
    try:
        html = _fetch_url(CLS_TELEGRAPH_URL)
        if not html:
            logger.warning("财联社 telegraph 页面为空")
            return items

        article_ids = _collect_cls_article_ids(html)
        if not article_ids:
            logger.warning("财联社 telegraph 未找到文章 ID")
            return items

        for article_id in article_ids:
            meta = _fetch_cls_article_meta(article_id)
            if not meta:
                continue
            title, url = meta
            item = _normalize_entry(title, title, url, "财联社")
            if item:
                items.append(item)
        logger.info("财联社采集 %d 条", len(items))
    except Exception as exc:
        logger.error("财联社采集失败: %s", exc)
    return items


def fetch_thepaper_energy() -> list[dict]:
    """澎湃新闻能源频道 - 列表页 HTML 解析."""
    items: list[dict] = []
    seen: set[str] = set()
    try:
        html = _fetch_url(THEPAPER_ENERGY_URL)
        if not html:
            return items

        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href*='/newsDetail_forward_']"):
            href = link.get("href", "")
            url = href if href.startswith("http") else f"https://www.thepaper.cn{href}"
            if url in seen:
                continue
            seen.add(url)

            title = _extract_link_title(link)
            if not title or len(title) < 5:
                continue

            # 已是能源频道列表，不再二次关键词过滤
            item = _normalize_entry(
                title,
                title,
                url,
                "澎湃",
                skip_keyword_filter=True,
            )
            if item:
                items.append(item)
        logger.info("澎湃能源频道采集 %d 条", len(items))
    except Exception as exc:
        logger.error("澎湃能源频道抓取失败: %s", exc)
    return items


def fetch_eia_rss() -> list[dict]:
    """EIA Today in Energy RSS."""
    items: list[dict] = []
    try:
        feed = _parse_feed(EIA_RSS_URL)
        if feed.bozo and not feed.entries:
            logger.warning(
                "EIA RSS 解析异常: %s",
                getattr(feed, "bozo_exception", feed.bozo),
            )
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            url = entry.get("link", "")
            item = _normalize_entry(
                title, summary, url, "EIA", _parse_date(entry), skip_keyword_filter=True
            )
            if item:
                items.append(item)
        logger.info("EIA 采集 %d 条", len(items))
    except Exception as exc:
        logger.error("EIA RSS 抓取失败: %s", exc)
    return items


def fetch_all_rss() -> list[dict]:
    """Aggregate all RSS / list sources."""
    cls_items = fetch_cls_rss()
    thepaper_items = fetch_thepaper_energy()
    eia_items: list[dict] = []
    if config.ENABLE_EIA_RSS:
        eia_items = fetch_eia_rss()
    else:
        logger.info("EIA RSS 已关闭（ENABLE_EIA_RSS=false）")
    all_items = cls_items + thepaper_items + eia_items
    logger.info(
        "RSS 采集完成，共 %d 条（财联社 %d，澎湃 %d，EIA %d）",
        len(all_items),
        len(cls_items),
        len(thepaper_items),
        len(eia_items),
    )
    return all_items
