# FinkiBOT - Smart College Assistant for FINKI

FinkiBOT scrapes the official FINKI site (`finki.ukim.mk`) and the student-run
[finki-hub.com](https://finki-hub.com), indexes everything into a RAG-ready vector
store (Postgres + pgvector), and gives students a few ways to use it:

- **Chat** - ask a question, get a cited answer grounded in what's actually indexed;
  the assistant picks search tools itself (announcements, courses, staff, exam dates,
  theses...) and falls back to a live search of finki.ukim.mk
- **Search** - raw ranked results instead of an LLM-written answer
- **Quiz maker** - generates quiz questions from an uploaded PDF/PPTX
- **Subscribe** - email alerts when new announcements match your keywords/courses
- **Insights** - a dashboard with counts of what's indexed
- **MCP tools playground** - FinkiBOT's MCP tools, runnable and inspectable directly
  on the site
- **Widget** - an embeddable chat (`/widget`) that a WordPress plugin can put on
  finki.ukim.mk

Three **MCP servers** (`official_mcp`, `finki_hub_mcp` and `official_live_mcp`) expose
that data as standardized MCP tools - the first two read the local index, the third
searches finki.ukim.mk live. See [`backend/mcp_servers/`](backend/mcp_servers).

## Layout

```
backend/    FastAPI app, scrapers, RAG/ingestion pipeline, MCP servers, notifier, quiz logic
frontend/   React web app (chat, search, quiz, subscribe, insights, MCP playground)
wordpress-widget/   WordPress plugin that embeds the chat widget on another site
```

For module-by-module detail and known scraper gaps, see
[backend/README.md](backend/README.md).

## Prerequisites

- **Docker Desktop**, running - used for the database and two small helper tools
- **Python 3.12** and **Node 22** - the backend and frontend run directly on your machine
- A free **Gemini API key** - [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (no card required)

The database (Postgres), a fake mail inbox (Mailhog) and a database browser (Adminer)
run in Docker. The backend API and the website run on your machine, so saving a code
change reloads it right away. (If you'd rather not install Python and Node, see
"Run everything in Docker instead" near the bottom.)

## First-time setup

Run these once, in order, from the repo root.

```bash
# 1. Make your own settings file from the template, then open backend/.env and fill in:
#      GEMINI_API_KEY  - from the link above; needed for chat and the quiz maker
#      JWT_SECRET_KEY  - any long random string; needed for logins. Make one with:
#                        python -c "import secrets; print(secrets.token_hex(32))"
cp backend/.env.sample backend/.env

# 2. Start the database + helper tools in Docker, in the background
docker compose up -d

# 3. Make an isolated Python environment for the backend and install its libraries
python -m venv .venv
.venv\Scripts\Activate.ps1                        # Windows PowerShell
#   macOS / Linux instead:  source .venv/bin/activate
pip install -r backend/requirements.txt

# 4. Create the database tables (this is Alembic - see "Database changes" below)
alembic -c backend/alembic.ini upgrade head

# 5. Load a saved snapshot of scraped data + create a dev admin login.
#    A few minutes, fully offline - the snapshot already includes the embeddings.
python -m backend.scripts.seed

# 6. Install the website's libraries
cd frontend
npm install
cd ..
```

The snapshot in step 5 (`backend/seed/documents.json.gz`) is from some point in the past,
so it may be missing the newest announcements - that's expected. See "Loading and
refreshing data" below to pull current data.

## Running it (every day)

Three things run at the same time, so open three terminal tabs. Run everything from
the repo root unless a step says otherwise.

**Tab 1 - database + helper tools (Docker):**
```bash
docker compose up -d          # "-d" = in the background. Once per work session
                              # (or after a reboot). Stop later with: docker compose down
```

**Tab 2 - backend API:**
```bash
.venv\Scripts\Activate.ps1                        # switch on the Python environment (every new tab)
alembic -c backend/alembic.ini upgrade head       # apply any new database changes; does nothing if there are none
uvicorn backend.api.main:app --reload --reload-dir backend
```
`--reload` restarts the API for you whenever you save a `.py` file. Leave it running.

**Tab 3 - website:**
```bash
cd frontend
npm run dev                   # leave running; refreshes the page when you save frontend files
```

Then open:

| What | URL |
|---|---|
| The app | http://localhost:8080 |
| API reference (auto-generated) | http://localhost:8000/docs |
| Mailhog - shows subscription emails (none are really sent) | http://localhost:8025 |
| Adminer - browse the database by hand | http://localhost:8090 - server `db`, username / password / database all `finkibot` |

## Updating after `git pull`

After pulling new code, run whichever of these apply. If unsure, run all three - each
does nothing when there's nothing to do.

```bash
.venv\Scripts\Activate.ps1

# 1. Backend libraries changed?  (backend/requirements.txt was in the pull)
pip install -r backend/requirements.txt

# 2. Database changed?  (a new file appeared in backend/alembic/versions/)
alembic -c backend/alembic.ini upgrade head

# 3. Website libraries changed?  (frontend/package.json or package-lock.json was in the pull)
cd frontend && npm install && cd ..
```

Then restart Tab 2 and Tab 3 (Ctrl+C, run the command again) - auto-reload only
watches your code, not newly installed libraries.

`git diff --stat HEAD@{1} HEAD` shows what a pull actually changed.

## Database changes (Alembic)

Which tables and columns the database has is defined by numbered files in
`backend/alembic/versions/`. **Alembic** is the tool that applies them. Always run it
from the repo root with `-c backend/alembic.ini`, or it won't find its files.

```bash
# Apply everything not yet applied - run after setup and after every git pull.
# Safe anytime; it skips whatever is already done.
alembic -c backend/alembic.ini upgrade head

# Am I up to date? These two should print the same number.
alembic -c backend/alembic.ini current    # where the database is
alembic -c backend/alembic.ini heads      # where the code expects it to be

# You edited backend/models.py? Generate a change file, eyeball it, then apply it.
alembic -c backend/alembic.ini revision --autogenerate -m "what you changed"
#   → open the new file in backend/alembic/versions/ and check it looks sane
alembic -c backend/alembic.ini upgrade head

# Undo the most recent change.
alembic -c backend/alembic.ini downgrade -1
```

## Loading and refreshing data

The database starts empty; step 5 of setup fills it from the saved snapshot. To pull
fresh data from the live sites later:

```bash
.venv\Scripts\Activate.ps1
python -m backend.scripts.reindex frequent   # announcements + quick sources - seconds
python -m backend.scripts.reindex slow       # course syllabi, professor pages - minutes
```

Add `--incremental` to fetch **only pages not already in the database** - much faster
(it skips every page it already has), but it won't notice edits to pages already
stored. Use it for a quick "pick up anything new" pass; run a plain (full) reindex now
and then to catch changes to existing pages:

```bash
python -m backend.scripts.reindex slow --incremental
```

The admin panel's **Reindex** section has the same two modes: the cadence buttons plus
a "New documents only (faster)" checkbox.

This never happens on its own in dev. Your data survives restarts - it lives in a
Docker volume named `finkibot_pgdata`, separate from the containers. The only things
that wipe it are `docker compose down -v` (the `-v` deletes volumes) or removing that
volume by hand.

Maintainers: after building up fresh data, `python -m backend.scripts.export_seed`
rewrites `backend/seed/documents.json.gz` so the next person's setup starts closer to
current - commit the changed file like any other change. (The admin panel's
**Reindex** button already does this after each run.)

## Accounts and admin access

Chat/search/quiz/subscribe work with no account at all, same as always. Accounts only
exist to gate the admin panel (`/admin` - user management, live-editable scraper/
scheduler settings). Registration (`/register`) is open to anyone but never grants
admin rights by itself.

`python -m backend.scripts.seed` (setup step 5) also creates a default admin account
for local dev, so there's always a way into `/admin` on a fresh machine without SMTP
set up: **`admin@email.com` / `admin`**. Change its password after logging in, or use
it only for local dev - for anything shared/deployed, promote a real account instead:

```bash
.venv\Scripts\Activate.ps1
# 1. Register normally through the site (or POST /auth/register) first
# 2. Then promote that account from the command line:
python -m backend.scripts.create_admin you@example.com
```

## Running the tests

```bash
.venv\Scripts\Activate.ps1
pytest backend/tests
```

## Handy commands

```bash
docker compose ps                 # which containers are running
docker compose logs -f db         # follow a container's logs (db / mailhog / adminer)
docker compose down               # stop the containers (your data stays - see above)
```

The first time you start the backend it downloads the embedding model
(`BAAI/bge-m3`, ~2 GB) into `~/.cache/huggingface`. That happens once; later starts
are fast.

## Run everything in Docker instead (optional)

If you'd rather not install Python and Node - or you just want to check the container
build still works - you can run the whole stack in Docker:

```bash
docker compose --profile full up --build
```

`--profile full` adds the `backend` and `frontend` containers; a plain
`docker compose up` leaves them out (that's what the everyday setup above relies on).
Run the data commands inside the container, e.g.:

```bash
docker compose exec backend python -m backend.scripts.seed
docker compose exec backend python -m backend.scripts.reindex frequent
```

Code still hot-reloads in this mode, but the frontend starts much more slowly and its
file-watcher sometimes misses edits on Windows - `docker compose restart frontend` if
a change doesn't show up. Editing `backend/.env` needs
`docker compose up -d --force-recreate backend` to take effect.

## Where the LLM is used

1. **Chat** (`/chat`) - the model calls search tools over the index (and a live site
   search as a fallback), then streams back a cited answer.
2. **Quiz generation** (`/quiz/upload`) - turns an uploaded PDF/PPTX into structured
   quiz questions. Deliberately upload-only, not RAG-based off indexed content -
   the scrapers only cover public metadata (course names/tags, announcements), not
   actual lecture material, so course-based quizzes were too shallow to be useful.
3. **Embeddings** - a local model (`BAAI/bge-m3`), not an API call, since content is
   mostly Macedonian and this avoids per-embedding cost.

Scraping, normalization, and the email notifier are deliberately LLM-free - search and
MCP tools return raw indexed data, not generated text.

Uses the **Gemini API free tier**, with **Groq** as a fallback when Gemini is out of
quota. The Gemini model (`gemini-2.5-flash` or `gemini-3.1-flash-lite`, each with its
own daily quota) and the preferred provider can be switched in the admin panel. Google
may use free-tier prompts to improve their products, worth knowing if students upload
their own materials to the quiz maker. Provider code lives in
`backend/core/llm_providers.py`; the quiz uses Gemini directly
(`backend/quiz/generation.py`).

## What's indexed right now

finki-hub.com is preferred wherever it has the data - cheap single JSON fetches vs.
finki.ukim.mk's one-request-per-item pages with no bulk endpoint. Official is only
scraped for what finki-hub genuinely doesn't have (or doesn't have in full: syllabus
prose beyond finki-hub's course metadata).

| Source | Content | Scraper |
|---|---|---|
| finki-hub.com | Course listing (level, semester, professors, prerequisites, accreditation) | `finki_hub.courses` |
| finki-hub.com | Teaching staff directory (title, position, cabinet, email, consultations) | `finki_hub.staff` |
| finki-hub.com | Exam-session schedules - the spreadsheets/PDFs are downloaded and parsed, so exam dates can be looked up | `finki_hub.sessions` |
| finki-hub.com | Professors' consultation slots | `finki_hub.consultations` |
| finki-hub.com | Recorded-lecture links & notes per course | `finki_hub.recordings` |
| finki-hub.com | Bachelor and master theses - title, abstract, mentor, committee, status, PDF link (student index only, no names) | `finki_hub.thesis_archive` |
| finki.ukim.mk | Announcement board | `official.announcements` |
| finki.ukim.mk | Events, projects, and jobs/internships (WordPress REST API) | `official.events`, `official.projects`, `official.jobs_and_internships` |
| finki.ukim.mk | PDFs linked from the site's pages - rulebooks, statutes, guides, forms | `official.linked_documents` |
| finki.ukim.mk | Exam-session schedule reference links (from the announcement board widget) | `official.schedule_links` |
| finki.ukim.mk | Official course syllabus prose - objectives, content outline, literature (capped, see `SCRAPE_SUBJECTS_LIMIT`) | `official.subjects` |
| finki.ukim.mk | Professor bios/publications (finki-hub's staff directory has contact info only, no bios) | `official.professors` |
| finki.ukim.mk | Static info pages - About Us, Studies, Admissions (quotas/requirements/documents per study cycle), International Students, Contact | `official.info_pages` |

**Not yet implemented** (registered but disabled in `backend/scrapers/registry.py`,
so a reindex skips them instead of failing): class schedules (`rasporedi.finki-hub.com`).

If you saved the admin Settings before the thesis scraper existed, it's stored as
switched off - tick `finki_hub.thesis_archive` in Admin → Settings.

**Known broken:** none currently. The previous `official.pages` (static info pages)
was removed because its only discovery mechanism (finki.ukim.mk's WordPress sitemap)
dead-redirects after the site's redesign; `official.info_pages` replaces it with a
hand-curated URL list (same fix `official.professors` got for its own listing page -
see its docstring) covering the student-relevant subset of About Us/Studies/
Admissions/International Students/Contact. Deliberately excludes legal/procurement/
finance/reports pages, English-only duplicates, and PDF-only content - see
`info_pages.py`'s docstring for the full reasoning.

## A quick heads-up if something's not scraping right

The scrapers target live external sites that occasionally change their HTML/URL
structure - if a reindex comes back oddly empty or search results look off, that's
usually the first thing to check, not a bug in the pipeline itself.
