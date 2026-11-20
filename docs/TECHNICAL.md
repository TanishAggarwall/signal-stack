# Signal Stack: Technical Documentation

## 1. Architecture

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI (Python 3.12+) | REST API under `/api`, background jobs in threads with one heavy job per company at a time |
| Storage | SQLAlchemy → SQLite (local) / Postgres (hosted) | 14 tables; every reported signal traces to `Signal → Document → Source → URL` |
| AI | Groq `openai/gpt-oss-120b` + Gemini `flash-lite` (free tiers) | JSON-only prompts, throttling, 429/5xx cooldown and provider fallback; prompts > 14k chars go to Gemini first (Groq free tier is 8k tokens/min) |
| Search | `ddgs` metasearch (Google/Bing HTML), DuckDuckGo/Bing News, GDELT DOC 2.0 API | Free, low-volume, used for discovery and news-query monitors |
| Crawling | httpx + trafilatura + feedparser + BeautifulSoup | robots.txt per host, per-domain delay (2 s), no auth bypass |
| Scheduling | APScheduler (per-company cron) + GitHub Actions cron → `/api/cron/{weekly,audit}` | Missed/failed runs are logged in `job_runs` and surfaced in the dashboard |
| Frontend | React 19 + TypeScript + Vite + Tailwind 4 + Recharts | 10 pages, light/dark, polling job tray |

Main tables: `companies`, `profile_facts`, `interview_turns`, `competitors`, `sources`, `source_checks`, `documents`, `signals`, `briefs`, `brief_actions`, `uploads`, `job_runs`, `audits`, `context_changes`.

## 2. Company research and interview
- **Research** (`services/research.py`) reads the homepage and up to 8 linked pages (about, product and pricing first). It uses full visible text when the main-content extractor returns little, and adds about 12 third-party search snippets.
- The LLM returns facts marked `verified` or `assumption`. A verified fact must name a fetched URL and a quote. `quote_in_text()` normalises Unicode and punctuation and checks that the quote really occurs in that page. If it doesn't, the fact is downgraded to `assumption`.
- **Interview** (`services/interview.py`) covers 10 topics: revenue lines, best customers, customer problems, why us, competitors, market changes, material risks, growth priorities, internal data and decisions.
  - Each question is generated from the profile and the transcript so far, picking a remaining topic.
  - A shingle-similarity check against earlier questions blocks repeats.
  - Each answer is turned into `founder` facts by one LLM call, which also decides on at most one follow-up (4 in total).
  - Skipped answers are recorded as confidential. Edited answers replace the facts that came from that answer.

## 3. Source discovery (Signal Stack)
1. **Competitors.** Five or more search queries ("X competitors", "X alternatives", "best <keyword> companies", …) and the competitors the founder named feed an LLM that proposes 7–10 candidates, each with a reason. A second, independent LLM pass rejects anything that does not serve the same customers or problem. If fewer than 5 survive, a wider second round runs. Missing websites are found by search.
2. **Competitor sources.** Each competitor gets:
   - a news-index monitor (news search on its name)
   - its own feed, if it has one
   - its top-level newsroom/blog, pricing and careers pages, found from the homepage links or by probing `/blog`, `/press` or `/pricing`
3. **Customer and market sources.** The LLM plans queries in the customer's own words (forums, Q&A, reviews) and regulator or trade-publication queries for the company's geographies. Each candidate URL is then **probed**:
   - robots.txt
   - HTTP status
   - RSS/Atom detection
   - date of the latest item
   - a count of article links (as a freshness proxy)
4. **Justification.** The LLM judges each usable candidate for Specific, Recent and Credible, and writes a reason for keeping it. Measured freshness overrides the LLM's guess for Recent.
5. **Approval.** Sources whose average score is ≥ 0.62 and Specific ≥ 0.6 are auto-approved; the rest stay `proposed` for the founder to approve. URLs blocked by robots.txt are listed in the job result.
6. **Context change** (`services/audit.py: reassess_context`). The LLM re-scores every approved source against the new context. Sources that no longer fit go back to `proposed` with a stated reason, new sources are discovered with the new focus, and a before/after record is stored.

## 4. Crawling and monitoring
- **`news_query`:** DuckDuckGo/Bing News plus GDELT results. The original article is fetched when robots.txt allows; otherwise only the headline and snippet are stored, marked `full_text=false`.
- **`rss`:** new feed entries; the article text is fetched where allowed.
- **`web`:** each visit stores a text snapshot. A changed hash produces a "Change detected" document containing only the added lines (difflib), which is how pricing and positioning changes are caught. New article links on listing pages are followed.
- **Freshness:** a lookback window (30 days for the first brief, 10 days for scheduled runs) and at most 8 new items per source per run.
- **Duplicates:** checked three ways: same normalised URL, same content hash, and near-duplicates (5-word-shingle Jaccard ≥ 0.6). Near-duplicates from other domains are kept as **corroboration**.
- **Health and history:** every check writes a `source_checks` row (status, HTTP code, items seen, new, duplicates, changed). Health is one of `ok`, `stale`, `dead`, `blocked` or `error`.

## 5. AI analysis
- **Pre-filter:** a cheap keyword and competitor-name filter discards clearly irrelevant documents before any LLM call.
- **Batches:** 4 documents per call (2,600 characters each), along with the profile and the founder's priorities.
- **Output:** for each document, the LLM decides whether it is a signal and returns:
  - **facts:** title, what happened, event date and a verbatim evidence quote
  - **interpretation:** why it matters, business area, opportunity/threat/neutral, impact 1–5, urgency 1–5, relevance 0–1, a suggested action and the competitor involved
- **Rejection:** a signal whose quote is not found in the stored text is discarded and counted as `rejected_unverified_quote` in the job stats.
- **Internal files:** CSV, Excel, PDF and text are parsed to text, analysed in chunks for objections, lost-deal reasons, product requests, sales patterns, risks and operational issues, and quote-verified against the file.

## 6. Ranking
`score = 100 × (0.25·relevance + 0.20·impact + 0.12·urgency + 0.15·source_reliability + 0.10·evidence_strength + 0.10·recency + 0.08·novelty)`

| Measure | How it is computed |
|---|---|
| **Source reliability** | Starts from the source's Credible score. Raised for government, education and major-publication domains, and for first-party competitor pages; lowered when only a snippet was accessible. |
| **Evidence strength** | Verified quote, plus full text, plus up to 2 corroborating documents from other domains. |
| **Recency** | `exp(-age_days/21)` |
| **Novelty** | 1 − maximum similarity to signals from earlier weeks |
| **Verification label** | `corroborated` / `single-source` / `internal`. Kept separate from the AI's relevance judgement, which is never treated as proof. |

Each signal stores a plain-language `rank_explanation` naming its top drivers and any weak measures.

## 7. Brief generation
- **Period:** from the last brief to now (or the lookback window for the first brief).
- **Category sections** (customers, competitors, market, internal) are rendered directly from the ranked signals.
- **Synthesis:** a single LLM call writes the executive summary, opportunities, risks, actions and watch-list from the top 25 signals. **Any item without valid signal IDs is dropped.**
- **Honesty:** if fewer than 3 opportunities are supported, the limitation is stated rather than filled. Empty sections say "No meaningful … development".
- **Actions** become `brief_actions` rows with an owner, priority and status that can be tracked in the UI.
- **Exports:** Markdown and email-ready HTML.

## 8. Reliability
- **Job logging:** every job (manual, schedule, cron) is a `job_runs` row with progress, stats and the error with its traceback.
- **Interrupted jobs:** jobs left `running` when the server restarts are marked failed with an explanation.
- **Missed runs:** APScheduler's missed-run events are written as failed runs.
- **Partial runs:** an LLM batch failure leaves its documents unanalysed for the next run and sets the job to `partial`.
- **Fault isolation:** one failing source never stops a crawl; its health and error are recorded.
- **Free-host sleep:** GitHub Actions wakes the API and calls the token-protected cron endpoint.
