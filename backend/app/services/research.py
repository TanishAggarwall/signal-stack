"""Step 2: initial company research. Reads the company's own site + public web mentions, then builds a
profile where every 'verified' line is backed by a quote we can find in a page we fetched."""
import json
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ..fetch import domain, extract_main_text, fetch, page_links, quote_in_text
from ..llm import complete_json
from ..models import Company, ProfileFact
from ..search import web_search

PAGE_HINTS = ("about", "service", "product", "pricing", "price", "course", "solution", "team", "company",
              "who-we-are", "how-it-works", "feature", "partner", "university", "plans", "customers", "why")

PROFILE_FIELDS = [
    "what_they_do", "products_services", "customer_segments", "business_model", "geography",
    "positioning", "differentiators", "industry", "pricing", "scale_and_traction",
]


SKIP = ("login", "signin", "signup", "register", "privacy", "terms", "cookie", "cart", "careers", "contact", "faq")


def _pick_internal_pages(html: str, base: str, limit: int = 8) -> list[str]:
    """Prefer about/product/pricing-type pages, then other top-level navigation pages."""
    d = domain(base)
    seen, hinted, other = set(), [], []
    for href, text in page_links(html, base):
        if domain(href) != d:
            continue
        path = urlparse(href.strip()).path.lower().rstrip("/")
        if not path or path in seen or path.count("/") > 2 or re.search(r"\.(pdf|jpg|png|zip)$", path):
            continue
        if any(s in path for s in SKIP):
            continue
        seen.add(path)
        key = path + " " + text.lower()
        (hinted if any(h in key for h in PAGE_HINTS) else other).append(href.strip())
    return (hinted + [o for o in other if "blog" not in o])[:limit]


def _page_text(html: str, url: str) -> tuple[str, str]:
    """Company pages: marketing copy is often outside the 'main article', so fall back to all visible text."""
    title, text, _ = extract_main_text(html, url)
    if len(text) < 1500:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()
        full = "\n".join(l for l in soup.get_text("\n", strip=True).splitlines() if len(l) > 2)
        if len(full) > len(text):
            text = full
    return title, text


def gather_pages(website: str, progress=lambda m: None) -> list[dict]:
    if not website.startswith("http"):
        website = "https://" + website
    pages = []
    progress(f"Reading {website}")
    home = fetch(website)
    if not home.ok:
        raise RuntimeError(f"Could not read the company website ({home.error or home.status}). "
                           "Check the URL; we do not bypass robots.txt or access restrictions.")
    title, text = _page_text(home.text, home.url)
    pages.append({"url": home.url, "title": title, "text": text[:6000]})
    for url in _pick_internal_pages(home.text, home.url):
        progress(f"Reading {url}")
        r = fetch(url)
        if r.ok and "html" in r.content_type:
            t, txt = _page_text(r.text, r.url)
            if len(txt) > 200:
                pages.append({"url": r.url, "title": t, "text": txt[:3000]})
    return pages


def run_research(db: Session, company: Company, progress=lambda m: None) -> dict:
    pages = gather_pages(company.website, progress)
    progress("Searching public mentions")
    mentions = web_search(f'"{company.name}"', 8) + web_search(f"{company.name} reviews", 6)
    own = domain(company.website)
    mentions = [m for m in mentions if domain(m["url"]) != own][:12]

    corpus = "\n\n".join(f"[PAGE {i}] {p['url']}\nTITLE: {p['title']}\n{p['text']}" for i, p in enumerate(pages))
    web = "\n".join(f"[WEB {i}] {m['url']} | {m['title']} | {m['snippet']}" for i, m in enumerate(mentions))

    progress("Building company profile")
    data = complete_json(
        f"""Company name: {company.name}
Website: {company.website}

Below is text we fetched from the company's own website, followed by third-party search results.
Build an initial company intelligence profile.

RULES
- A claim is "verified" ONLY if it is directly stated in the PAGE/WEB text. Then give source_url (copied exactly
  from the [PAGE]/[WEB] header) and an evidence quote copied word-for-word from that text (10-30 words).
- Anything you infer (likely segments, likely competitors, likely business model) must be "assumption",
  with a short note on why you infer it in "evidence".
- Do not invent numbers, customers, funding or partners.

Return JSON:
{{
 "summary": "2-3 sentence plain description",
 "industry": "short industry label",
 "keywords": ["8-15 search keywords describing the problem space, products and market (not the brand)"],
 "facts": [{{"field": one of {PROFILE_FIELDS}, "value": "...", "status": "verified|assumption",
            "source_url": "...", "evidence": "..."}}],
 "open_questions": ["things the website does not answer that the founder interview should cover"]
}}
Aim for 12-20 facts covering every field.

=== COMPANY WEBSITE ===
{corpus[:24000]}

=== THIRD-PARTY SEARCH RESULTS ===
{web[:5000]}
""",
        max_tokens=6000,
    )

    texts = {p["url"]: p["text"] for p in pages} | {m["url"]: f"{m['title']} {m['snippet']}" for m in mentions}
    db.query(ProfileFact).filter(ProfileFact.company_id == company.id, ProfileFact.status != "founder").delete()
    verified = assumed = 0
    for f in data.get("facts", []):
        value = (f.get("value") or "").strip()
        if not value:
            continue
        status = f.get("status", "assumption")
        src, ev = f.get("source_url", ""), f.get("evidence", "")
        if status == "verified":
            # downgrade any 'verified' claim whose quote is not really in the page it cites
            page_text = texts.get(src) or next((t for u, t in texts.items() if u.rstrip("/") == src.rstrip("/")), "")
            if not page_text or not quote_in_text(ev, page_text):
                status = "assumption"
                ev = f"(AI inference; quote could not be matched in source) {ev}"
        verified += status == "verified"
        assumed += status == "assumption"
        db.add(ProfileFact(company_id=company.id, field=f.get("field", "other")[:80], value=value,
                           status=status, source_url=src if status == "verified" else "", evidence=ev[:1000]))
    company.summary = data.get("summary", "")[:2000]
    company.industry = data.get("industry", "")[:200]
    company.keywords = [k for k in data.get("keywords", []) if isinstance(k, str)][:20]
    if company.stage == "created":
        company.stage = "researched"
    db.commit()
    return {"pages_read": len(pages), "mentions": len(mentions), "verified_facts": verified,
            "assumptions": assumed, "open_questions": data.get("open_questions", [])}


def profile_text(db: Session, company: Company, max_chars: int = 7000) -> str:
    facts = db.query(ProfileFact).filter(ProfileFact.company_id == company.id).all()
    lines = [f"Company: {company.name} ({company.website})", f"Industry: {company.industry}",
             f"Summary: {company.summary}"]
    order = {"founder": 0, "verified": 1, "assumption": 2}
    for f in sorted(facts, key=lambda x: order.get(x.status, 3)):
        lines.append(f"- [{f.status}] {f.field}: {f.value}")
    return "\n".join(lines)[:max_chars]


def profile_json(db: Session, company: Company) -> str:
    facts = db.query(ProfileFact).filter(ProfileFact.company_id == company.id).all()
    return json.dumps([{"field": f.field, "value": f.value, "status": f.status} for f in facts])
