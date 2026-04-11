# Intern Opportunity Intelligence Agent (Canada focus)

Production-minded MVP: aggregate internship postings from multiple sources, deduplicate, score relevance with an LLM, and send high-signal alerts via Telegram.

## Features

- **Sources**: curated GitHub README (markdown table), Prosple, TalentEgg, Eluta (Canada) — see [Why each source helps](#why-each-source-helps-you-find-jobs) below
- **Pipeline**: scrape → normalize → **focus role keyword filter** (from [`user_profile.yaml`](user_profile.yaml), compiled in `app/utils/role_keywords.py`) → hash dedupe → **Gemini** (or OpenAI) scoring (`match_score`, `reason`, `tags` only; **priority** is keyword-derived) → Telegram notifications
- **Scheduler**: APScheduler runs the full pipeline every **6 hours** (configurable)
- **API**: `GET /jobs`, `GET /jobs/high-priority`, `POST /run-scan` or `POST /jobs/run-scan`, `GET /scan-status` or `GET /jobs/scan-status`
- **Web dashboard** at `/` (static HTML/JS): table, filters, run-scan, **`applied_at`** with `PATCH /jobs/{id}/applied`; client loads **all pages** of `/jobs` (or `/jobs/high-priority` when **High signal** is on) so the full result set is available (scroll the table)

## Why each source helps you find jobs

Each feed answers a different “where do postings actually show up?” problem. Together they reduce blind spots: one site might list a role another never crawls.

| Source | What it is | Why it helps |
|--------|----------------|--------------|
| **GitHub README (Simplify-style list)** | A large, community-maintained **markdown table** of internships (company, role, location, apply link), usually tracking **US + international** postings in one place. | **Breadth and speed**: many tech internships are aggregated in one file; you get direct application links and a consistent snapshot without visiting dozens of career sites. Good for **discovering names and links** you might miss if you only browse Canadian job boards. |
| **Prosple (Canada)** | A **Canadian student / early-career** job search site (`ca.prosple.com`), oriented toward internships and new grads. | **Canada-first listings** and employer pages aimed at students — strong for roles that are advertised for the Canadian market rather than only on US boards. Complements the GitHub list when your priority is **local eligibility and location**. |
| **TalentEgg** | A **Canadian** early-career platform (`talentegg.ca`) with employer postings and student-focused roles. | **Another Canadian channel**: employers often post here who may not appear on Prosple or on the big US internship README. Adds **diversity of employers** (industries and company sizes) so you are not relying on a single board. |
| **Eluta** | **Canadian job search** (`eluta.ca`) with organic HTML job listings (e.g. by role slug or search). | **General Canadian job market** coverage beyond “student-only” sites — useful for **software and related roles** that are posted like standard jobs. Helps when internships or junior roles are listed on broad job search engines rather than only on campus boards. |

**Important**: All sources pass the same **focus role keyword** gate. Rules live in **[`user_profile.yaml`](user_profile.yaml)** (`keywords:`); edit that file to personalize filters and LLM profile (`profile:`). **Restart `uvicorn`** after changes (patterns load at import). If a posting’s title/company/description does not match any **keyword group**, it is dropped before LLM scoring.

## Requirements

- **Python 3.11+**
- **Playwright** with **Chromium** (installed after dependencies; used for Prosple, TalentEgg, Eluta)
- Optional: **Google Gemini** or **OpenAI** API key for LLM scoring; **Telegram** bot for alerts

## Local deploy (what to do end-to-end)

This is the practical checklist behind “clone, configure, run.” The **step-by-step commands** are in [Local installation (detailed)](#local-installation-detailed) below.

1. **Install Python dependencies**  
   Use **Python 3.11+**, create and activate a virtual environment, then `pip install -r requirements.txt` (see sections 2–3 there).

2. **Install Playwright’s Chromium**  
   Run `playwright install chromium` **in the same venv** as the app. Several scrapers (Prosple, TalentEgg, Eluta) need a real browser; skipping this step usually causes browser-related errors on scan.

3. **Configure `.env` and API keys**  
   Copy `.env.example` to `.env` (never commit `.env`). Set at least **`GEMINI_API_KEY`** (recommended) **or** **`OPENAI_API_KEY`** so the pipeline can score jobs and fill `match_score`, `reason`, and `tags`. Add Telegram variables only if you want notifications.

4. **Customize keywords in `user_profile.yaml`**  
   Role gating and LLM context come from **[`user_profile.yaml`](user_profile.yaml)** (`keywords:` for which postings are kept, `profile:` for how the model describes you). **Adjust keyword groups to match your own direction** (stack, title patterns, seniority). The sample committed in this repo is oriented toward **frontend, backend, and full-stack** style roles as a starting point—replace or extend groups as needed.

5. **Restart the server after YAML changes**  
   Keyword patterns and profile text are loaded **at process start**. After editing `user_profile.yaml`, **restart `uvicorn`**. Optionally run `python scripts/validate_user_profile.py` first to catch YAML/regex issues.

6. **Data stays on your machine**  
   Stored jobs live in **`data/*.db`** (SQLite; listed in `.gitignore`). A fresh clone has **no rows** until you run **Run scan** or wait for the scheduler. To wipe local postings, delete `data/*.db` and restart the app.

## Local installation (detailed)

These steps assume you clone the repo to your machine and run everything **locally** (no cloud deploy required). Data is stored in a **SQLite file** under `./data/` by default.

### 1. Clone and enter the project

```bash
git clone https://github.com/YOUR_ACCOUNT/job_hunter.git
cd job_hunter
```

### 2. Create a virtual environment

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install the Chromium browser for Playwright

Scrapers for several sources use a real browser context:

```bash
playwright install chromium
```

### 5. Configure environment variables (never commit secrets)

Secrets and machine-local settings live in **`.env`**, which is **gitignored** (see `.gitignore`). Start from the template:

```bash
cp .env.example .env
```

Edit **`.env`** in your editor and set at least:

- **`GEMINI_API_KEY`** (recommended) **or** **`OPENAI_API_KEY`** — required for meaningful job scoring, tags, and reasons. Without a key, scoring may fail or return empty/low signal depending on code paths.
- Optionally **`TELEGRAM_BOT_TOKEN`** and **`TELEGRAM_CHAT_ID`** if you want scan alerts.

Never commit `.env`. Share only `.env.example` in Git.

### 6. Create the data directory

The default database URL is `sqlite:///./data/intern_intel.db`:

```bash
mkdir -p data
```

On first run, the app will create the SQLite file if it does not exist.

### 7. Run the API and open the dashboard

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Health**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Trigger a full scan** (browser): use **Run scan** on the page, or:

```bash
curl -X POST http://127.0.0.1:8000/run-scan
```

Poll **`GET /jobs/scan-status`** until the pipeline is idle, then refresh the table.

### 8. Validate `user_profile.yaml` (optional)

After editing keywords or `profile`, check for YAML/regex errors **before** restarting the server:

```bash
python scripts/validate_user_profile.py
```

Optional path: `python scripts/validate_user_profile.py /path/to/user_profile.yaml`. Exit code **0** means no blocking errors; warnings (e.g. zero keyword groups) are printed to stderr.

### 9. Run tests (optional)

```bash
pytest -q
```

### Troubleshooting

| Issue | What to try |
|-------|----------------|
| `playwright` / browser errors | Run `playwright install chromium` again; ensure you are in the same venv where `playwright` is installed. |
| Scoring always empty or errors | Set **`GEMINI_API_KEY`** or **`OPENAI_API_KEY`** in `.env` and restart `uvicorn`. |
| Permission / port in use | Change port: `uvicorn app.main:app --host 127.0.0.1 --port 8001`. |
| No jobs from a source | Check logs; external sites change HTML. Some listings are also **filtered out** by the global role keyword gate. |
| Edited `user_profile.yaml` but no change | Restart **`uvicorn`**; keyword and profile YAML are read at process start. |

## Web dashboard

After the server is running, open **http://127.0.0.1:8000/** for a table with refresh, **High signal** / **Canada** filters, **Run scan**, and **Mark applied** (`PATCH /jobs/{id}/applied`).

- **High signal**: loads **`GET /jobs/high-priority`** (same pagination behavior as `/jobs`). Uncheck to use the full list from **`GET /jobs`**.
- **Canada**: **client-side** filter in [`app/static/app.js`](app/static/app.js). The API still returns all stored rows; the checkbox **hides** rows that match US-focused heuristics (US state names and `City, ST` codes, major US metros, explicit **USA** / **United States** / “remote in USA”, and similar). This is not a SQL filter and is not perfect on messy location text; uncheck **Canada** to see everything. After changing dashboard JS, do a **hard refresh** in the browser (or restart `uvicorn` if you rely on cached assets).

Static assets live under `app/static/` and are served from `/static/...`.

**Location text in the table** comes from scrapers plus optional **detail-page enrichment** (JSON-LD `JobPosting`): multiple `jobLocation` values are joined with **`; `**, and obviously glued strings (e.g. missing spaces after state codes) are normalized in [`app/utils/job_location_html.py`](app/utils/job_location_html.py) and again for display in the dashboard JS.

## API list ordering

`GET /jobs` and `GET /jobs/high-priority` return rows in this order:

1. **Priority** — `HIGH`, then `MEDIUM`, then `LOW` (priority comes only from keyword-group hit counts in [`user_profile.yaml`](user_profile.yaml)).
2. **Intern-style titles first** — within the same priority, postings whose **title** looks like intern / internship / co-op / similar (see `app/api/routes/jobs.py`) are listed before other roles.
3. **`match_score`** descending (nulls last).
4. **`created_at`** descending.

## Environment variables

See [`.env.example`](.env.example) for every variable and inline comments. Summary:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL (default: SQLite file under `./data/`) |
| `GEMINI_API_KEY` | Job relevance scoring (**preferred** if set; [Google AI Studio](https://aistudio.google.com/apikey)) |
| `GEMINI_MODEL` | e.g. `gemini-2.0-flash` |
| `OPENAI_API_KEY` | Scoring if Gemini key is empty |
| `OPENAI_MODEL` | e.g. `gpt-4o-mini` |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Target chat or channel ID |
| `GITHUB_INTERNSHIPS_*` | README URL and row cap for the GitHub table source |
| `PROSPLE_SEARCH_URL` | Prosple search URL |
| `TALENTEGG_INTERNSHIPS_URL` | TalentEgg listing URL |
| `ELUTA_*` | Enable Eluta, list URL, caps |
| `JOB_LOCATION_DETAIL_FETCH_ENABLED` | If `true`, GET listing URLs’ job pages to read city/region from JSON-LD (default on; set `false` to shorten scans) |
| `JOB_LOCATION_DETAIL_MAX_PER_SOURCE` | Cap on detail fetches per source per scan |
| `JOB_LOCATION_DETAIL_DELAY_SEC` | Pause between detail requests (rate limiting) |
| `SCAN_INTERVAL_HOURS` | Scheduler interval (default `6`) |

## Sample Telegram notification

When a job is **HIGH** priority or **match_score > 0.75**, the bot can send HTML like:

```text
Software Engineering Intern
Acme Corp
Score: 0.82
Priority: HIGH

Strong match: backend role in Canada; mentions media tooling.

Apply / details → (link)
```

(Exact wording comes from the LLM `reason` field.)

## Notes

- External site HTML changes may break Prosple/TalentEgg/Eluta selectors; scrapers log errors and other sources continue.
- TalentEgg: legacy paths such as `/internships/` may return HTTP **500**; default URL **`/latest-jobs`** (`TALENTEGG_INTERNSHIPS_URL`). **US-only** TalentEgg cards are dropped at scrape time. Rows must also pass the **global role keyword** gate ([`user_profile.yaml`](user_profile.yaml) → `app/utils/role_keywords.py`).
- **Role keywords** (all sources): only jobs whose title/company/description match at least one keyword **group** in `user_profile.yaml` are scored and stored. **Priority** (`HIGH` / `MEDIUM` / `LOW`) comes only from how many distinct groups match (`priority_from_focus_group_hits`): 1 group → LOW, 2–3 → MEDIUM, 4+ → HIGH. The LLM supplies **`match_score`**, **`reason`**, and **`tags`** only (no model-assigned priority).
- GitHub source parses the configured README URL (markdown table with Company / Role / Location / Application columns).
