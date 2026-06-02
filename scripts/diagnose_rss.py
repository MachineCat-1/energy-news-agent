"""Quick RSS source diagnostic."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import feedparser
import requests
from bs4 import BeautifulSoup

import config
from collector.rss_fetcher import (
    _is_energy_related,
    fetch_cls_rss,
    fetch_eia_rss,
    fetch_thepaper_energy,
)

print("=== 财联社 telegraph ===")
html = requests.get(
    "https://www.cls.cn/telegraph",
    headers={"User-Agent": config.USER_AGENT},
    timeout=15,
).text
import re

ids = list(dict.fromkeys(re.findall(r"share/article/(\d+)", html)))
print("article ids in page:", len(ids))

print("\n=== EIA RSS ===")
feed2 = feedparser.parse("https://www.eia.gov/rss/todayinenergy.xml")
print("entries:", len(feed2.entries))
print("bozo:", feed2.bozo)
if feed2.bozo:
    print("bozo_exception:", getattr(feed2, "bozo_exception", None))

print("\n=== 澎湃 HTML ===")
try:
    resp = requests.get(
        "https://www.thepaper.cn/channel_25950",
        headers={"User-Agent": config.USER_AGENT},
        timeout=15,
    )
    print("status:", resp.status_code, "html_len:", len(resp.text))
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select("a[href*='/newsDetail_forward_']")
    print("links found:", len(links))
    for link in links[:5]:
        title = link.get_text(strip=True)
        print(f"  - {title[:50]} | energy={_is_energy_related(title, title)}")
except Exception as exc:
    print("ERROR:", exc)

print("\n=== fetch_* 函数结果 ===")
cls_items = fetch_cls_rss()
thepaper_items = fetch_thepaper_energy()
eia_items = fetch_eia_rss()
print("cls:", len(cls_items))
print("thepaper:", len(thepaper_items))
print("eia:", len(eia_items))
print("total:", len(cls_items) + len(thepaper_items) + len(eia_items))
