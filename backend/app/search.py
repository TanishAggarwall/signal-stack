"""Free discovery/search layer (no paid APIs):
- web search: `ddgs` metasearch (Google/Bing HTML backends, used at low volume)
- news search: `ddgs` news (DuckDuckGo/Bing News) + GDELT DOC 2.0 API (public, free)
- Bing News RSS (robots.txt permits it)
"""
import logging
import time
import warnings
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser

from .fetch import fetch

warnings.filterwarnings("ignore")
log = logging.getLogger("search")

_BAD_HOST_PARTS = ("bing.com/aclick", "googleadservices", "doubleclick", "/aclk?")


def _ddgs():
    from ddgs import DDGS
    return DDGS(timeout=15)


def web_search(query: str, max_results: int = 8) -> list[dict]:
    """Returns [{title, url, snippet}]"""
    for backend in ("google", "bing", "duckduckgo", "brave"):
        try:
            rows = _ddgs().text(query, max_results=max_results, backend=backend)
        except Exception as e:  # backend rate-limited or empty -> try next
            log.debug("search %s failed on %s: %s", query, backend, e)
            continue
        out = [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in rows
            if r.get("href", "").startswith("http") and not any(b in r.get("href", "") for b in _BAD_HOST_PARTS)
        ]
        if out:
            return out
        time.sleep(1)
    return []


def _parse_dt(s) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y%m%dT%H%M%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:25] if "T" in s and "-" in s else s, fmt)
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


def news_search(query: str, max_results: int = 15, timelimit: str = "m") -> list[dict]:
    """[{title, url, snippet, published, publisher}] from news indexes. timelimit: d|w|m"""
    for backend in ("duckduckgo", "bing", "yahoo"):
        try:
            rows = _ddgs().news(query, max_results=max_results, timelimit=timelimit, backend=backend)
        except Exception as e:
            log.debug("news %s failed on %s: %s", query, backend, e)
            continue
        if rows:
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("body", ""),
                    "published": _parse_dt(r.get("date")),
                    "publisher": r.get("source", ""),
                }
                for r in rows if r.get("url")
            ]
    return []


def gdelt_search(query: str, max_records: int = 25, timespan: str = "30d") -> list[dict]:
    q = quote_plus(query)
    url = (f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}%20sourcelang:english"
           f"&mode=artlist&format=json&maxrecords={max_records}&sort=datedesc&timespan={timespan}")
    r = fetch(url, api=True)
    if not r.ok or not r.text.strip().startswith("{"):
        return []
    import json
    try:
        arts = json.loads(r.text).get("articles", [])
    except json.JSONDecodeError:
        return []
    return [
        {"title": a.get("title", ""), "url": a.get("url", ""), "snippet": "",
         "published": _parse_dt(a.get("seendate")), "publisher": a.get("domain", "")}
        for a in arts if a.get("url")
    ]


def bing_news_rss(query: str) -> list[dict]:
    url = f"https://www.bing.com/news/search?q={quote_plus(query)}&format=rss"
    r = fetch(url)
    if not r.ok:
        return []
    return parse_feed(r.text)


def parse_feed(xml: str) -> list[dict]:
    feed = feedparser.parse(xml)
    out = []
    for e in feed.entries[:60]:
        pub = None
        for k in ("published_parsed", "updated_parsed"):
            if getattr(e, k, None):
                pub = datetime(*getattr(e, k)[:6])
                break
        summary = e.get("summary", "") or ""
        if "<" in summary:
            from bs4 import BeautifulSoup
            summary = BeautifulSoup(summary, "lxml").get_text(" ", strip=True)
        src = e.get("source", {})
        out.append({
            "title": e.get("title", ""),
            "url": e.get("link", ""),
            "snippet": summary[:2000],
            "published": pub,
            "publisher": src.get("title", "") if isinstance(src, dict) else "",
        })
    return out
