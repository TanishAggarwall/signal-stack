<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:7B3FF2,100:2A1066&height=230&section=header&text=Signal%20Stack&fontSize=62&fontColor=FFFFFF&animation=fadeIn&fontAlignY=32&desc=AI-Powered%20Business%20Intelligence%20%C2%B7%20Monday%20Morning%20Brief&descAlignY=52&descSize=17" width="100%"/>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=21&duration=3000&pause=900&color=7B3FF2&center=true&vCenter=true&width=760&lines=Research.+Interview.+Monitor.+Brief.;From+Newsletters+to+an+Intelligence+Layer;Every+signal+quoted+from+a+real+source;Customers+%C2%B7+Competitors+%C2%B7+Market+%C2%B7+Internal" alt="Typing SVG" />

<br>

![Status](https://img.shields.io/badge/STATUS-WORKING%20PROTOTYPE-7B3FF2?style=for-the-badge&labelColor=000000)
![Cost](https://img.shields.io/badge/COST-%E2%82%B90%20%C2%B7%20FREE%20TIERS%20ONLY-7B3FF2?style=for-the-badge&labelColor=000000)
![Demo](https://img.shields.io/badge/DEMO-MEETUNIVERSITY-7B3FF2?style=for-the-badge&labelColor=000000)

![AI](https://img.shields.io/badge/AI-GROQ%20%2B%20GEMINI%20FREE%20TIER-FFFFFF?style=for-the-badge&labelColor=7B3FF2)
![Evidence](https://img.shields.io/badge/EVIDENCE-VERBATIM%20QUOTE%20CHECK-FFFFFF?style=for-the-badge&labelColor=7B3FF2)
![Crawler](https://img.shields.io/badge/CRAWLER-ROBOTS.TXT%20RESPECTED-FFFFFF?style=for-the-badge&labelColor=7B3FF2)

<br>

![Python](https://img.shields.io/badge/Python-000000?style=flat-square&logo=python&logoColor=9A72F5)
![FastAPI](https://img.shields.io/badge/FastAPI-000000?style=flat-square&logo=fastapi&logoColor=9A72F5)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-000000?style=flat-square&logo=sqlalchemy&logoColor=9A72F5)
![PostgreSQL](https://img.shields.io/badge/Postgres%20%2F%20SQLite-000000?style=flat-square&logo=postgresql&logoColor=9A72F5)
![APScheduler](https://img.shields.io/badge/APScheduler-000000?style=flat-square&logo=clockify&logoColor=9A72F5)
![React](https://img.shields.io/badge/React-000000?style=flat-square&logo=react&logoColor=9A72F5)
![TypeScript](https://img.shields.io/badge/TypeScript-000000?style=flat-square&logo=typescript&logoColor=9A72F5)
![Tailwind](https://img.shields.io/badge/Tailwind-000000?style=flat-square&logo=tailwindcss&logoColor=9A72F5)
![Recharts](https://img.shields.io/badge/Recharts-000000?style=flat-square&logo=chartdotjs&logoColor=9A72F5)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-000000?style=flat-square&logo=githubactions&logoColor=9A72F5)

</div>
<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=Demo&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>

[![Watch the demo](https://img.shields.io/badge/▶%20WATCH%20DEMO-7B3FF2?style=for-the-badge&labelColor=000000)](#)
[![Live app](https://img.shields.io/badge/🌐%20LIVE%20APP-7B3FF2?style=for-the-badge&labelColor=000000)](#)
[![Sample briefs](https://img.shields.io/badge/📄%20SAMPLE%20BRIEFS-7B3FF2?style=for-the-badge&labelColor=000000)](samples/)

</div>
<br>

> **Signal Stack** turns a company into a continuously monitored, intelligent business. Enter a company name and website: it **researches** the business (separating verified facts from assumptions), runs an **adaptive 10-question founder interview**, **discovers and justifies** intelligence sources across **Customers, Competitors, Market and Internal** data, **crawls** them politely, **analyses and ranks** what changed, and writes an executive **Monday Morning Brief**, with every development linked to its source. Nothing about a company is hard-coded: a company it has never seen gets the same treatment.

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=System%20Architecture&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>
</div>

```mermaid
flowchart TD
    U[👤 Founder: name + website] --> R[🔎 Research<br/>site pages + public mentions]
    R --> P[(🧾 Intelligence Profile<br/>verified · assumption · founder)]
    P --> I[💬 Adaptive Interview<br/>10 questions + follow-ups]
    I --> P
    P --> D[🧭 Source Discovery<br/>web search → probe → justify]
    D --> SS[🗂️ Signal Stack<br/>Customers · Competitors · Market · Internal]
    SS --> C[🕷️ Crawler<br/>robots.txt · rate limits · change detection · dedup]
    UP[📁 CSV / Excel / PDF / text uploads] --> C
    C --> DOC[(📚 Documents<br/>evidence + links + history)]
    DOC --> A[🧠 Analysis<br/>LLM must quote the source verbatim]
    A --> RK[📊 Ranking<br/>relevance · impact · urgency · reliability · evidence · recency · novelty]
    RK --> B[📰 Monday Morning Brief]
    SCH[⏰ APScheduler + GitHub Actions cron] --> C
    SCH --> AU[🩺 Monthly Source Audit]
    AU --> SS

    style A fill:#7B3FF2,color:#fff
    style B fill:#19181e,color:#fff
    style SS fill:#e9f4d4,color:#000
    style DOC fill:#2A1066,color:#fff
```

**Key rule:** the LLM is an analyst, never a source. It only reads documents we collected, must copy an evidence quote word-for-word, and **code rejects any signal whose quote is not found in the stored text**. Verified facts and AI interpretation are stored in separate fields and shown separately.

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=How%20It%20Works&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>
</div>

| Stage | What happens | Guard-rail |
|---|---|---|
| 🔎 **Research** | Reads the homepage + up to 8 key pages, plus public search mentions | A "verified" fact must cite a fetched page **and** a quote found in it, otherwise it is downgraded to "assumption" |
| 💬 **Interview** | 10 core questions generated from the profile and previous answers, one at a time, with ≤4 follow-ups | Duplicate-question check; skip for confidential; answers editable later and re-extracted |
| 🧭 **Discovery** | Competitors from search + founder answers (second LLM pass rejects unrelated names); sources found by search, then probed | robots.txt, liveness, RSS detection and freshness are **measured**, not guessed; each source gets a reason + Specific / Recent / Credible scores |
| 🕷️ **Monitoring** | RSS, page-change diffs, competitor newsrooms/pricing/careers pages, news-index queries (DuckDuckGo/Bing News + GDELT) | Per-domain delay, no auth bypass, 401/403/429 respected, exact + near-duplicate detection, full check history |
| 🧠 **Analysis** | Batches of documents → signal / not signal; what happened, when, why it matters, area, type, urgency, action | Verbatim-quote verification; facts vs interpretation stored apart |
| 📊 **Ranking** | `25% relevance · 20% impact · 12% urgency · 15% source reliability · 10% evidence · 10% recency · 8% novelty` | Reliability, evidence strength and relevance are **separate measures**; corroboration across domains raises evidence; each rank has a written explanation |
| 📰 **Brief** | 10 required sections; category sections rendered straight from signals; LLM only synthesises | Every summary/opportunity/risk/action must cite existing signal IDs or it is dropped; empty sections say so |

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=Monday%20Morning%20Brief&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>
</div>

| # | Section | Built from |
|:---:|---|---|
| 1 | Executive Summary (top 5) | LLM synthesis, each line cites signals |
| 2 | Customer Signals | Ranked customer signals |
| 3 | Competitor Intelligence | Ranked competitor signals (what changed, evidence, why it matters) |
| 4 | Market Intelligence | Regulatory / industry / economic / technology signals |
| 5 | Internal Business Intelligence | Insights from uploaded CRM / transcripts / reports |
| 6 | Opportunities Identified | Evidence, impact, next step, priority |
| 7 | Risks & Threats | Impact + urgency |
| 8 | Recommended Actions for This Week | Owner + priority, **trackable in the UI** |
| 9 | What We Should Watch | Early developments |
| 10 | Source Appendix | Source, link, published date, discovered date, snippet, verification + confidence |

Export: **Markdown**, **email-ready HTML**, copy to clipboard. Brief history is kept per company.

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=Automation&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>
</div>

| Process | Default schedule | Steps |
|---|---|---|
| **A · Weekly Intelligence Brief** | Monday 07:00 (company time zone) | crawl approved sources → detect changes → analyse → rank → save brief |
| **B · Monthly Signal Stack Audit** | 1st of month | dead URLs · blocked · duplicates · inactive · declining relevance · new candidates → health report + add/remove recommendations |
| Monitoring crawl | every 24 h (configurable) | collect between briefs |

Both run in-process (APScheduler, per-company settings) **and** via a free GitHub Actions cron (`.github/workflows/scheduled-runs.yml`) because free hosts sleep. Every run, including missed and failed ones, is logged and shown in **Settings & Automation**. Briefs can also be triggered manually.

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=Setup%20Instructions&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>
</div>

```bash
git clone https://github.com/<your-username>/signal-stack.git
cd signal-stack
```

### 🔧 Backend (Python 3.12+)
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env          # add your free GROQ_API_KEY and GEMINI_API_KEY
uvicorn app.main:app --port 8000
```

### 💻 Frontend
```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

### 🧪 Reproduce the demo
1. **Company Setup** → `MeetUniversity` · `https://www.meetuniversity.com`
2. **AI Interview** → answer the 10 questions (skip any confidential one)
3. **Signal Stack** → *Build Signal Stack*; approve/remove sources in **Source Manager**
4. **Run brief** (top bar) → read it in **Monday Brief**, export Markdown/HTML
5. Repeat for two companies from other industries; then change one company's context in **Intelligence Profile → Change business context**

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=Deployment%20(Free)&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>
</div>

| Part | Host | How |
|---|---|---|
| API | **Render** free web service | `render.yaml` blueprint (root `backend/`); set `GROQ_API_KEY`, `GEMINI_API_KEY`, `DATABASE_URL` |
| Database | **Neon** free Postgres | `postgresql+psycopg://…?sslmode=require` (Render free disks are not persistent) |
| Frontend | **Vercel** free | root `frontend/`, env `VITE_API_URL=https://<api>.onrender.com` |
| Scheduler | **GitHub Actions** | repo secrets `API_URL`, `CRON_TOKEN` |

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=Project%20Structure&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>
</div>

```
backend/app/
  main.py            REST API (FastAPI)          models.py     schema (Signal → Document → Source)
  llm.py             Groq + Gemini, fallback     fetch.py      robots.txt, rate limits, extraction, quote check
  search.py          free web/news search        scheduler.py  weekly brief + monthly audit
  jobs.py            logged background jobs      pipelines.py  job bodies
  services/  research · interview · discovery · crawler · analysis · ranking · brief · internal · audit
frontend/src/
  pages/     Overview · Setup · Profile · Interview · Stack · Sources · Feed · Brief · Internal · Automation
docs/        TECHNICAL.md · COST.md · TEST_EVIDENCE.md
samples/     generated Monday briefs (Markdown)
```

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rounded&color=0:7B3FF2,100:2A1066&height=90&section=header&text=Honest%20Limitations&fontSize=34&fontColor=FFFFFF&fontAlignY=60&width=1200" width="100%"/>
</div>

- **Blocked by robots.txt, so skipped:** Reddit, Quora, LinkedIn, Google News RSS and some review sites. Customer-voice coverage is therefore thinner than it would be with paid/official APIs.
- **Free LLM quotas:** Groq ≈ 8k tokens/min, Gemini free-tier rate limits. Large runs queue, retry and fall back; a full first run takes several minutes.
- **News indexes** sometimes give only a headline/snippet when the publisher blocks crawlers; such signals are labelled *snippet only* and get lower reliability.
- **Scanned PDFs** need OCR (not included).

Full details: [`docs/TECHNICAL.md`](docs/TECHNICAL.md) · [`docs/COST.md`](docs/COST.md)

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=rect&color=0:7B3FF2,100:2A1066&height=4&width=1200" width="100%"/>
</div>

<div align="center">

**Built by Tanish Aggarwal** · EDXSO AI Engineer Intern Assignment

UI visual language inspired by the *CRM UI Charts for SaaS Dashboards* Figma kit by David Sedláček (CC BY 4.0).

</div>

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:7B3FF2,100:2A1066&height=120&section=footer&width=1200" width="100%"/>
</div>
