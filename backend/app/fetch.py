"""Polite HTTP layer: robots.txt, per-domain rate limiting, no auth bypass, text extraction."""
import hashlib
import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from bs4 import BeautifulSoup

from .config import HTTP_TIMEOUT, PER_DOMAIN_DELAY_SECONDS, USER_AGENT

log = logging.getLogger("fetch")

_client = httpx.Client(
    headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8"},
    timeout=HTTP_TIMEOUT,
    follow_redirects=True,
)
_robots: dict[str, RobotFileParser | None] = {}
_robots_lock = threading.Lock()
_domain_last: dict[str, float] = {}
_domain_lock = threading.Lock()


@dataclass
class FetchResult:
    url: str
    status: int | None
    text: str = ""
    content_type: str = ""
    error: str = ""
    blocked: bool = False

    @property
    def ok(self):
        return self.status is not None and 200 <= self.status < 300 and not self.blocked


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    scheme = p.scheme or "https"
    netloc = p.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", p.path) or "/"
    # drop tracking params
    q = "&".join(x for x in p.query.split("&") if x and not x.lower().startswith(("utm_", "fbclid", "gclid", "ref=")))
    return urlunparse((scheme, netloc, path, "", q, ""))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def _robots_for(url: str) -> RobotFileParser | None:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    with _robots_lock:
        if base in _robots:
            return _robots[base]
    rp = RobotFileParser()
    try:
        r = _client.get(base + "/robots.txt", timeout=10)
        if r.status_code in (401, 403):
            rp.disallow_all = True
        elif r.status_code >= 400:
            rp.allow_all = True
        else:
            rp.parse(r.text.splitlines())
    except httpx.HTTPError:
        rp = None  # robots unreachable -> treat as allowed but be extra polite
    with _robots_lock:
        _robots[base] = rp
    return rp


def robots_allowed(url: str) -> bool:
    rp = _robots_for(url)
    if rp is None:
        return True
    return rp.can_fetch(USER_AGENT, url)


def _wait_turn(url: str):
    d = domain(url)
    with _domain_lock:
        wait = _domain_last.get(d, 0) + PER_DOMAIN_DELAY_SECONDS - time.time()
        _domain_last[d] = max(time.time(), _domain_last.get(d, 0) + PER_DOMAIN_DELAY_SECONDS)
    if wait > 0:
        time.sleep(wait)


def fetch(url: str, check_robots: bool = True, api: bool = False) -> FetchResult:
    """GET a public URL. `api=True` is for documented public APIs (GDELT, HN Algolia) that are meant
    for programmatic access; robots.txt of the website is still checked for normal pages."""
    if check_robots and not api and not robots_allowed(url):
        return FetchResult(url, None, error="Disallowed by robots.txt", blocked=True)
    _wait_turn(url)
    try:
        r = _client.get(url)
    except httpx.HTTPError as e:
        return FetchResult(url, None, error=f"{type(e).__name__}: {e}"[:300])
    if r.status_code in (401, 403, 429):
        # we never try to get around auth walls, bot protection or rate limits
        return FetchResult(str(r.url), r.status_code, error=f"HTTP {r.status_code} (access restricted)", blocked=r.status_code != 429)
    return FetchResult(str(r.url), r.status_code, text=r.text, content_type=r.headers.get("content-type", ""),
                       error="" if r.is_success else f"HTTP {r.status_code}")


def extract_main_text(html: str, url: str = "") -> tuple[str, str, datetime | None]:
    """Return (title, main_text, published_date)."""
    title, published = "", None
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
        if meta:
            title = meta.title or ""
            if meta.date:
                try:
                    published = datetime.fromisoformat(meta.date[:10])
                except ValueError:
                    pass
    except Exception:  # trafilatura metadata can fail on odd markup
        pass
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True, favor_recall=True) or ""
    if not text:
        soup = BeautifulSoup(html, "lxml")
        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()
        text = re.sub(r"\s+\n", "\n", soup.get_text("\n", strip=True))
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    return title[:500], text, published


def page_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        if href.startswith("http"):
            out.append((href, a.get_text(" ", strip=True)[:200]))
    return out


def find_feeds(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    feeds = []
    for link in soup.find_all("link", rel=True, href=True):
        rel = " ".join(link.get("rel")).lower()
        typ = (link.get("type") or "").lower()
        if "alternate" in rel and ("rss" in typ or "atom" in typ):
            feeds.append(urljoin(base_url, link["href"]))
    return feeds


# ---------- evidence verification ----------

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9%$₹€£.,'\- ]+", " ", s).replace("  ", " ").strip()


def quote_in_text(quote: str, text: str) -> bool:
    """True if the quote (normalised) really appears in the collected text.
    Allows '...' elisions: each fragment must appear, in order."""
    q, t = _norm(quote), " ".join(_norm(text).split())
    if len(q) < 12:
        return False
    frags = [" ".join(f.split()) for f in re.split(r"\.\.\.|…", q) if len(f.strip()) >= 8]
    pos = 0
    for f in frags or [" ".join(q.split())]:
        i = t.find(f, pos)
        if i < 0:
            return False
        pos = i + len(f)
    return True


def shingles(text: str, k: int = 5) -> set[int]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {hash(" ".join(words[i:i + k])) for i in range(max(len(words) - k + 1, 1))}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
