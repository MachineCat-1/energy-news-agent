import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from bs4 import BeautifulSoup
import config

for url in [
    "http://www.nea.gov.cn/xwfb/index.htm",
    "http://www.nea.gov.cn/gjnyj/index.htm",
]:
    r = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=15)
    r.encoding = r.apparent_encoding or "gbk"
    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.select('a[href*=".htm"]'):
        h = a.get("href", "")
        t = a.get_text(" ", strip=True)
        if len(t) > 6:
            links.append({"t": t, "h": h})
    out = {"url": url, "count": len(links), "links": links[:20]}
    Path("data/nea_links.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(url, len(links))
