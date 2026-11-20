"""Internal intelligence: CSV / Excel / PDF / text uploads -> objections, lost-deal reasons, product requests,
sales patterns and risks, each backed by a verbatim quote from the uploaded file."""
import io
from pathlib import Path

import pandas as pd
from pypdf import PdfReader
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..fetch import quote_in_text, sha
from ..llm import LLMError, complete_json
from ..models import Company, Document, Signal, Source, Upload
from .research import profile_text

KINDS = {".csv": "csv", ".xlsx": "excel", ".xls": "excel", ".pdf": "pdf", ".txt": "text", ".md": "text"}
INSIGHT_TYPES = {"objection": "Recurring objection", "lost_deal": "Lost-deal reason", "product_request": "Product request",
                 "sales_pattern": "Sales pattern", "risk": "Emerging risk", "operational_issue": "Operational issue"}


def parse_file(name: str, data: bytes) -> tuple[str, str]:
    ext = Path(name).suffix.lower()
    kind = KINDS.get(ext)
    if not kind:
        raise ValueError(f"Unsupported file type {ext}. Use CSV, Excel, PDF or text.")
    if kind in ("csv", "excel"):
        df = pd.read_csv(io.BytesIO(data)) if kind == "csv" else pd.read_excel(io.BytesIO(data))
        df = df.dropna(how="all").fillna("")
        rows = [" | ".join(f"{c}: {v}" for c, v in r.items() if str(v).strip()) for _, r in df.head(400).iterrows()]
        text = f"Columns: {', '.join(map(str, df.columns))}\nRows: {len(df)}\n" + "\n".join(rows)
    elif kind == "pdf":
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:60])
    else:
        text = data.decode("utf-8", errors="ignore")
    return kind, text.strip()


def save_upload(db: Session, company: Company, filename: str, data: bytes, label: str = "") -> Upload:
    kind, text = parse_file(filename, data)
    if not text:
        raise ValueError("No readable text found in this file (scanned PDFs need OCR, which is not included).")
    folder = UPLOAD_DIR / str(company.id)
    folder.mkdir(parents=True, exist_ok=True)
    safe = Path(filename).name
    (folder / safe).write_bytes(data)
    src = db.query(Source).filter(Source.company_id == company.id, Source.category == "internal").first()
    doc = Document(company_id=company.id, source_id=src.id if src else None, url=f"upload://{company.id}/{safe}",
                   url_hash=sha(f"upload://{company.id}/{safe}/{sha(text)}"), title=f"Internal file: {safe}",
                   publisher=label or "Internal upload", content_hash=sha(text), text=text[:200000], full_text=True)
    db.add(doc)
    db.flush()
    up = Upload(company_id=company.id, filename=safe, kind=kind, label=label, chars=len(text), document_id=doc.id)
    db.add(up)
    db.commit()
    return up


def analyze_upload(db: Session, company: Company, up: Upload, progress=lambda m: None) -> dict:
    doc = db.get(Document, up.document_id)
    text = doc.text
    chunks = [text[i:i + 7000] for i in range(0, min(len(text), 28000), 7000)]
    prof = profile_text(db, company, 2500)
    made = rejected = 0
    for n, chunk in enumerate(chunks, 1):
        progress(f"Analysing {up.filename} part {n}/{len(chunks)}")
        try:
            data = complete_json(
                f"""{prof}

Internal file "{up.filename}" ({up.label or up.kind}), part {n}/{len(chunks)}:
\"\"\"{chunk}\"\"\"

Find RECURRING or decision-relevant internal insights: customer objections, lost-deal reasons, product requests,
sales patterns, emerging risks, operational issues. Count how many rows/mentions support each (estimate from the
text). Only report what the text supports.
Return JSON: {{"insights": [{{"type": one of {list(INSIGHT_TYPES)}, "title": "...", "what_happened": "factual
summary incl. frequency", "evidence_quote": "12-40 words copied EXACTLY from the text", "mentions": n,
"why_it_matters": "specific to {company.name}", "signal_type": "opportunity|threat|neutral", "impact": 1-5,
"urgency": 1-5, "relevance": 0-1, "consider_doing": "one concrete step"}}]}}""",
                max_tokens=4000, prefer="gemini")
        except LLMError:
            continue
        for r in data.get("insights", []):
            q = (r.get("evidence_quote") or "").strip()
            if not quote_in_text(q, chunk):
                rejected += 1
                continue
            t = r.get("type") if r.get("type") in INSIGHT_TYPES else "risk"
            db.add(Signal(company_id=company.id, document_id=doc.id, category="internal",
                          title=f"{INSIGHT_TYPES[t]}: {r.get('title', '')}"[:500], what_happened=r.get("what_happened", ""),
                          evidence_quote=q, quote_verified=True, verification="internal",
                          why_it_matters=r.get("why_it_matters", ""), business_area=INSIGHT_TYPES[t],
                          signal_type=r.get("signal_type") if r.get("signal_type") in ("opportunity", "threat", "neutral") else "neutral",
                          consider_doing=r.get("consider_doing", ""),
                          impact=max(1, min(5, int(r.get("impact") or 2))), urgency=max(1, min(5, int(r.get("urgency") or 2))),
                          relevance=max(0.0, min(1.0, float(r.get("relevance") or 0.6))), event_date=up.created_at))
            made += 1
    up.analyzed = True
    doc.analyzed, doc.relevant = True, made > 0
    db.commit()
    return {"insights": made, "rejected_unverified_quote": rejected}


def analyze_pending_uploads(db: Session, company: Company, progress=lambda m: None) -> dict:
    total = {"files": 0, "insights": 0}
    for up in db.query(Upload).filter(Upload.company_id == company.id, Upload.analyzed.is_(False)).all():
        r = analyze_upload(db, company, up, progress)
        total["files"] += 1
        total["insights"] += r["insights"]
    return total
