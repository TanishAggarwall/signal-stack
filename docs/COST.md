# Cost Statement

**Total running cost: ₹0.** No paid APIs, scraping platforms or paid AI services are used.

| Component | Service / tool | Tier | Limits that matter |
|---|---|---|---|
| LLM (primary) | Groq `openai/gpt-oss-120b` | Free | ~8,000 tokens/min, 1,000 requests/day; long prompts are sent to Gemini instead |
| LLM (fallback / long prompts) | Google Gemini `gemini-flash-lite-latest` | Free (AI Studio key) | Per-minute/day request caps; occasional 503 "high demand", handled by retry and fallback |
| Web discovery search | `ddgs` (open source) over public Google/Bing/DuckDuckGo results | Free | Low volume only; a backend may rate-limit, in which case the next is tried |
| News monitoring | DuckDuckGo/Bing News via `ddgs`, GDELT DOC 2.0 API | Free | GDELT asks for ≤1 request / 5 s; results can lag by hours |
| Crawling / parsing | httpx, trafilatura, feedparser, BeautifulSoup | Open source | robots.txt and access restrictions respected; blocked sites are skipped |
| Database | SQLite (local) / Neon Postgres | Free | Neon free: 0.5 GB storage |
| API hosting | Render web service | Free | Sleeps after ~15 min idle (cold start ~1 min); no persistent disk, hence Postgres |
| Frontend hosting | Vercel | Hobby (free) | Static SPA |
| Scheduler | APScheduler (in-process) + GitHub Actions cron | Free | Actions cron can start a few minutes late |

## Disclosed limitations
- Sources whose robots.txt disallows generic crawlers are **not** crawled: Reddit, Quora, LinkedIn, Google News RSS and some review sites.
- When a publisher blocks article fetching, only the news index's headline and snippet are stored, and the signal is marked *snippet only*.
- Free LLM quotas make a full first run take several minutes, and a large backlog may be split over runs. Documents that were not analysed are retried on the next run.
