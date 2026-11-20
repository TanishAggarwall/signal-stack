"""Central configuration, loaded from environment / backend/.env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'signalstack.db'}")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Order in which free LLM providers are tried. On a 429/5xx we fall through to the next.
LLM_ORDER = [p.strip() for p in os.getenv("LLM_ORDER", "groq,gemini").split(",") if p.strip()]

# Polite crawling
USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "SignalStackBot/0.1 (business-intelligence research prototype; respects robots.txt)",
)
PER_DOMAIN_DELAY_SECONDS = float(os.getenv("PER_DOMAIN_DELAY_SECONDS", "2.0"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "20"))

# Protects the /api/cron/* endpoints that an external free cron (GitHub Actions) can call.
CRON_TOKEN = os.getenv("CRON_TOKEN", "")
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
