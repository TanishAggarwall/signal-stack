"""Database schema. Every reported development traces back: Signal -> Document -> Source (URL)."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


DEFAULT_SETTINGS = {
    "briefing_day": "mon",
    "briefing_time": "07:00",
    "timezone": "Asia/Kolkata",
    "monitoring_frequency_hours": 24,
    "source_refresh_days": 7,
    "audit_day_of_month": 1,
    "lookback_days": 30,
}


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    # setup progress: created -> researched -> interviewed -> stack_ready -> monitoring
    stage: Mapped[str] = mapped_column(String(40), default="created")
    summary: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(200), default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    settings: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_SETTINGS))
    context_version: Mapped[int] = mapped_column(Integer, default=1)

    facts = relationship("ProfileFact", cascade="all, delete-orphan", back_populates="company")


class ProfileFact(Base):
    """One line of the company intelligence profile.
    status: verified (backed by a fetched page + quote), assumption (AI inference), founder (interview answer)."""
    __tablename__ = "profile_facts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="assumption")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    company = relationship("Company", back_populates="facts")


class InterviewTurn(Base):
    __tablename__ = "interview_turns"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(120))
    question: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    is_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Competitor(Base):
    __tablename__ = "competitors"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str] = mapped_column(String(500), default="")
    kind: Mapped[str] = mapped_column(String(40), default="direct")  # direct | substitute | indirect
    description: Mapped[str] = mapped_column(Text, default="")
    why_relevant: Mapped[str] = mapped_column(Text, default="")
    evidence_url: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="approved")  # proposed | approved | removed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(20))  # customers | competitors | market | internal
    kind: Mapped[str] = mapped_column(String(20))  # rss | web | news_query | hn_query | upload
    name: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(1500))
    query: Mapped[str] = mapped_column(String(500), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    competitor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    specific: Mapped[float] = mapped_column(Float, default=0.5)
    recent: Mapped[float] = mapped_column(Float, default=0.5)
    credible: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed | approved | removed
    discovered_by: Mapped[str] = mapped_column(String(40), default="discovery")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    # health
    health: Mapped[str] = mapped_column(String(20), default="unchecked")  # ok | dead | blocked | stale | error | unchecked
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_new_item: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    page_hash: Mapped[str] = mapped_column(String(64), default="")
    duplicate_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    removed_reason: Mapped[str] = mapped_column(Text, default="")


class SourceCheck(Base):
    """History of each crawl of each source."""
    __tablename__ = "source_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(20))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    new_items: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    changed: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text, default="")


class Document(Base):
    """A piece of raw evidence collected from a source (article, feed item, page change, uploaded file)."""
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(1500))
    url_hash: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(1000), default="")
    publisher: Mapped[str] = mapped_column(String(300), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    full_text: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analyzed: Mapped[bool] = mapped_column(Boolean, default=False)
    relevant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Signal(Base):
    """An analysed development. Facts (what/when/source/quote) are kept apart from interpretation."""
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    competitor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competitor_name: Mapped[str] = mapped_column(String(200), default="")
    # --- facts ---
    title: Mapped[str] = mapped_column(String(500))
    what_happened: Mapped[str] = mapped_column(Text)
    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evidence_quote: Mapped[str] = mapped_column(Text)
    quote_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification: Mapped[str] = mapped_column(String(30), default="single-source")  # corroborated | single-source | internal
    corroborating_doc_ids: Mapped[list] = mapped_column(JSON, default=list)
    # --- interpretation (AI) ---
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    business_area: Mapped[str] = mapped_column(String(120), default="")
    signal_type: Mapped[str] = mapped_column(String(20), default="neutral")  # opportunity | threat | neutral
    consider_doing: Mapped[str] = mapped_column(Text, default="")
    # --- scores (kept separate on purpose) ---
    impact: Mapped[int] = mapped_column(Integer, default=2)       # 1-5 (AI judgement)
    urgency: Mapped[int] = mapped_column(Integer, default=2)      # 1-5 (AI judgement)
    relevance: Mapped[float] = mapped_column(Float, default=0.5)  # strategic relevance 0-1
    source_reliability: Mapped[float] = mapped_column(Float, default=0.5)
    evidence_strength: Mapped[float] = mapped_column(Float, default=0.5)
    recency: Mapped[float] = mapped_column(Float, default=0.5)
    novelty: Mapped[float] = mapped_column(Float, default=1.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    rank_explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)


class Brief(Base):
    __tablename__ = "briefs"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    markdown: Mapped[str] = mapped_column(Text, default="")
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class BriefAction(Base):
    __tablename__ = "brief_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("briefs.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    signal_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | in_progress | done | dismissed


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    chars: Mapped[int] = mapped_column(Integer, default=0)
    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analyzed: Mapped[bool] = mapped_column(Boolean, default=False)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(40))
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual | schedule | cron
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | success | failed | partial
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    progress: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")


class Audit(Base):
    __tablename__ = "audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ContextChange(Base):
    __tablename__ = "context_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    change_text: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
