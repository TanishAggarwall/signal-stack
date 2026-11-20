from .services.discovery import probe


def classify_manual_source(url: str) -> tuple[str, str]:
    """For a founder-added URL: detect whether it is (or exposes) an RSS/Atom feed."""
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    p = probe(url)
    if p.get("feed"):
        return "rss", p["feed"]
    return "web", url
