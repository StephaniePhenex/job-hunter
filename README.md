# Intern Opportunity Intelligence Agent (Canada focus)

Production-minded MVP: aggregate internship postings from multiple sources, deduplicate, score relevance with an LLM, and send high-signal alerts via Telegram.

## Features

- **Sources**: GitHub curated README (markdown table), Prosple (Playwright), TalentEgg (Playwright)
- **Pipeline**: scrape → normalize → **focus role keyword filter** (all sources) → hash dedupe → **Gemini** (or OpenAI) scoring → Telegram notifications
- **Scheduler**: APScheduler runs the full pipeline every **6 hours** (configurable)
- **API**: `GET /jobs`, `GET /jobs/high-priority`, `POST /run-scan` (and `POST /jobs/run-scan`)
- **Day 7 bonus**: minimal **web dashboard** at `/` (static HTML/JS), job **`tags`** (JSON, from the LLM), **`applied_at`** with `PATCH /jobs/{id}/applied`

## Web dashboard (Day 7)

After `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`, open **http://127.0.0.1:8000/** for a read-only table with refresh, high-signal filter, run-scan, and **Mark applied** (calls `PATCH /jobs/{id}/applied` with `{"applied": true|false}`).

Static assets live under `app/static/` and are served from `/static/...`.

## Requirements

- Python 3.11+
- Playwright browsers (installed after `pip install`)
- Optional: **Google Gemini** or OpenAI API key for scoring; Telegram bot for alerts

## Setup

```bash
cd job_hunter
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Edit .env: GEMINI_API_KEY (recommended) or OPENAI_API_KEY, TELEGRAM_*, etc.
mkdir -p data
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET http://127.0.0.1:8000/health`
- Trigger scan: `POST http://127.0.0.1:8000/run-scan`

## Environment variables

See [`.env.example`](.env.example). Never commit real secrets.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL (default SQLite file under `./data/`) |
| `GEMINI_API_KEY` | Job relevance scoring (**used first** if set; [Google AI Studio](https://aistudio.google.com/apikey)) |
| `GEMINI_MODEL` | e.g. `gemini-2.0-flash` |
| `OPENAI_API_KEY` | Scoring if Gemini key is empty |
| `OPENAI_MODEL` | e.g. `gpt-4o-mini` |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Target chat or channel ID |
| `SCAN_INTERVAL_HOURS` | Scheduler interval (default `6`) |

## Sample Telegram notification

When a job is **HIGH** priority or **match_score > 0.75**, the bot sends HTML like:

```text
Software Engineering Intern
Acme Corp
Score: 0.82
Priority: HIGH

Strong match: backend role in Canada; mentions media tooling.

Apply / details → (link)
```

(Exact wording comes from the LLM `reason` field.)

## Tests

```bash
pytest -q
```

## Notes

- External site HTML changes may break Prosple/TalentEgg selectors; scrapers log errors and other sources continue.
- TalentEgg: legacy paths such as `/internships/` may return HTTP **500**; default URL **`/latest-jobs`** (`TALENTEGG_INTERNSHIPS_URL`). **US-only** cards are dropped at scrape time. Rows must also pass the **global role keyword** gate (see `app/utils/role_keywords.py`).
- **Role keywords** (all sources): only jobs whose title/company/description match at least one focus pattern are scored and stored. **Priority** (`HIGH` / `MEDIUM` / `LOW`) is derived from how many distinct keyword *groups* match (see `priority_from_focus_group_hits` in `app/utils/role_keywords.py`): 1 group → LOW, 2–3 → MEDIUM, 4+ → HIGH — overriding the LLM’s priority while keeping LLM `match_score`, `tags`, and blended `reason`.
- GitHub source parses the configured README URL (markdown table with Company / Role / Location / Application columns).
