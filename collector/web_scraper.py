import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

import config
from collector.rss_fetcher import _is_energy_related

logger = logging.getLogger(__name__)

# 非新闻页面路径片段（部门首页、导航页等）
_SKIP_PATH_PARTS = (
    "/sjzz/",
    "/ldhd/",
    "/zwgk/",
    "/hdjl/",
    "javascript:",
    "#",
)

# 能源局新闻列表页
NEA_LIST_URLS = (
    "http://www.nea.gov.cn/xwfb/index.htm",
    "http://www.nea.gov.cn/gjnyj/index.htm",
)


def _fetch_page(url: str) -> str | None:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        # 政府网站多为 GBK/GB2312
        if resp.encoding and resp.encoding.lower() in ("iso-8859-1", "ascii"):
            resp.encoding = resp.apparent_encoding or "gbk"
        return resp.text
    except Exception as exc:
        logger.warning("页面请求失败 %s: %s", url, exc)
        return None


def _normalize_url(href: str, base: str) -> str:
    if href.startswith("http"):
        return href.replace("https://www.nea.gov.cn", "http://www.nea.gov.cn")
    if href.startswith("/"):
        return f"http://www.nea.gov.cn{href}"
    base_dir = base.rsplit("/", 1)[0]
    return f"{base_dir}/{href}"


def _is_valid_news_link(url: str, title: str) -> bool:
    if not title or len(title) < 10:
        return False
    if url.endswith("index.htm"):
        return False
    if any(skip in url for skip in _SKIP_PATH_PARTS):
        return False
    if any(skip in title for skip in ("首页", "具体职责", "联系我们", "工作进展", "更多")):
        return False
    if "nea.gov.cn" in url and url.endswith(".htm"):
        return True
    if "jiemian.com" in url and "/article/" in url:
        return True
    return False


def _extract_article_body(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in (
        "article",
        ".article-content",
        ".article-main",
        ".news-content",
        ".content",
        ".article",
        "main",
    ):
        node = soup.select_one(selector)
        if node:
            text = node.get_text("\n", strip=True)
            if len(text) > 50:
                return text[:2000]
    paragraphs = soup.find_all("p")
    text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
    return text[:2000] if text else ""


def _make_item(title: str, url: str, summary: str, source: str) -> dict:
    import hashlib

    title = re.sub(r"\s+", " ", title).strip()
    return {
        "id": hashlib.md5(url.encode("utf-8")).hexdigest(),
        "title": title,
        "content": (summary or title)[:2000],
        "url": url,
        "source": source,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "category": "unknown",
        "tags": [],
    }


def fetch_jiemian_energy() -> list[dict]:
    """界面新闻能源频道."""
    items: list[dict] = []
    try:
        html = _fetch_page("https://www.jiemian.com/lists/2.html")
        if not html:
            return items
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("a[href*='/article/']")
        seen: set[str] = set()
        for link in links[:40]:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not title or len(title) < 8 or href in seen:
                continue
            url = href if href.startswith("http") else f"https://www.jiemian.com{href}"
            if not _is_valid_news_link(url, title):
                continue
            seen.add(href)
            time.sleep(2)
            article_html = _fetch_page(url)
            summary = _extract_article_body(article_html) if article_html else title
            # 能源频道本身已做主题筛选，不再二次过滤以免漏掉汽车/电力等关联报道
            items.append(_make_item(title, url, summary, "界面新闻"))
    except Exception as exc:
        logger.error("界面新闻抓取失败: %s", exc)
    return items


def fetch_nea_announcements() -> list[dict]:
    """国家能源局新闻公告 - 从新闻发布等列表页抓取."""
    items: list[dict] = []
    seen_urls: set[str] = set()
    try:
        for list_url in NEA_LIST_URLS:
            html = _fetch_page(list_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.select("a[href*='.htm']"):
                title = link.get_text(strip=True)
                href = link.get("href", "").strip()
                if not href:
                    continue
                url = _normalize_url(href, list_url)
                if url in seen_urls or not _is_valid_news_link(url, title):
                    continue
                seen_urls.add(url)
                time.sleep(2)
                article_html = _fetch_page(url)
                summary = _extract_article_body(article_html) if article_html else title
                if len(summary) < 20:
                    summary = title
                if not _is_energy_related(title, summary):
                    continue
                items.append(_make_item(title, url, summary, "国家能源局"))
                if len(items) >= 15:
                    break
            if len(items) >= 15:
                break
    except Exception as exc:
        logger.error("国家能源局抓取失败: %s", exc)
    return items


def fetch_all_web() -> list[dict]:
    items: list[dict] = []
    items.extend(fetch_jiemian_energy())
    items.extend(fetch_nea_announcements())
    logger.info("网页采集完成，共 %d 条", len(items))
    return items
