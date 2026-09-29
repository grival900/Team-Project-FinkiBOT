# Backend

FastAPI app, scrapers, ingestion/RAG pipeline, MCP servers, notifier, and quiz logic.

## Layout

| Path | Purpose |
|---|---|
| `api/` | FastAPI app + routers (`search`, `documents`, `chat`, `quiz`, `subscribe`/announcements, `auth`, `admin`, `mcp_tools`, `courses`, `insights`) |
| `core/` | Shared config, LLM client wrapper (`llm.py`, `llm_providers.py`), the chat internals (`chat_prompt.py`, `chat_tools.py`, `chat_ranking.py`, `chat_sources.py`), `exam_schedule.py` (exam dates parsed from the indexed schedules), `theses.py`, `prerequisites.py`, `insights.py`, `transliteration.py`, `retrieval.py` (the one place vector search lives), `auth.py` (password hashing, JWT, `get_current_user`/`require_admin`), `users.py` (admin user-management guards), `site_settings.py` (admin-editable operational settings, DB-backed) |
| `scrapers/official_site/` | `announcements.py` (the board), `wp_posts.py` (events, projects, jobs/internships), `linked_documents.py` (PDFs linked from pages), `schedule_links.py` (exam-session schedule reference links), `subjects.py` (official course syllabus prose - the gap on top of `finki_hub.courses`), `professors.py` (bios/publications - the gap on top of `finki_hub.staff`), `info_pages.py` (About Us/Studies/Admissions/International Students/Contact - hand-curated URL list, see its docstring) |
| `scrapers/finki_hub/` | `courses.py` (course listing), `staff.py` (teaching staff), `consultations.py` (consultation slots), `sessions.py` (exam session schedules), `recordings.py` (recorded-lecture links/notes), `thesis_archive.py` (bachelor/master theses); `schedules.py` is a disabled stub - see Known gaps |
| `scrapers/` (root) | `normalize.py` (common schema), `registry.py` (what `/admin/reindex` runs), `http.py` (shared rate-limited client) |
| `ingestion/` | Chunking, local embeddings (BGE-M3), pgvector indexing |
| `mcp_servers/` | `official_mcp/` and `finki_hub_mcp/` (thin tool layers over `core/retrieval.py`) and `official_live_mcp/` (live search of finki.ukim.mk, no local index) |
| `notifier/` | Subscription management, filter-matching diff, SMTP sending |
| `quiz/` | LLM quiz generation from an uploaded PDF/PPTX + text extraction (upload-only - see root README's "Where the LLM is used") |
| `models.py`, `db.py` | SQLAlchemy models and session setup |
| `alembic/` | DB migrations |
| `scheduler.py` | Periodic scrape → index → notify job (APScheduler) |
| `scripts/` | `reindex.py` (manual scrape + index), `seed.py`/`export_seed.py` (fast offline bootstrap from `seed/documents.json.gz` - see "First-time setup" in the root README), `create_admin.py` (promotes an already-registered user to admin - see root README's "Accounts and admin access"), `dedupe_documents.py` (one-off cleanup of duplicate documents) |
| `tests/` | Unit tests - pure-logic and fixture-based, no live network or DB required |

## Local dev (without Docker)

```bash
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r backend/requirements.txt

cp .env.sample .env  # fill in GEMINI_API_KEY at minimum for /chat and /quiz
alembic -c backend/alembic.ini upgrade head  # requires a running Postgres (see root docker-compose.yml)

uvicorn backend.api.main:app --reload
```

Run the test suite (no live services needed):

```bash
pytest backend/tests
```

Populate the database (fast, offline, no live scraping) from the bundled seed -
this is the recommended way to bootstrap a fresh Postgres, and is what a new machine
should run first (see "First-time setup" in the root README):

```bash
python -m backend.scripts.seed
```

Run an MCP server standalone (e.g. to point an MCP inspector at it):

```bash
python -m backend.mcp_servers.official_mcp.server
python -m backend.mcp_servers.finki_hub_mcp.server
python -m backend.mcp_servers.official_live_mcp.server
```

Trigger a manual scrape + index pass (also wired to a **Reindex** button on the admin
panel's Settings tab):

```bash
curl -X POST http://localhost:8000/admin/reindex               # everything
curl -X POST "http://localhost:8000/admin/reindex?cadence=frequent"  # cheap sources only
curl -X POST "http://localhost:8000/admin/reindex?cadence=slow"      # expensive sources only
curl -X POST "http://localhost:8000/admin/reindex?incremental=true"  # only fetch URLs not already indexed
curl http://localhost:8000/admin/reindex/status                 # progress + per-scraper diff of the last run
```

The run is asynchronous (returns immediately); `GET /admin/reindex/status` reports
`running` → `done`/`error` with a per-scraper `new`/`updated`/`unchanged` breakdown,
which is what the admin panel's button polls to show its progress bar and result.

`incremental=true` (also the admin panel's "New documents only" checkbox, and
`python -m backend.scripts.reindex ... --incremental`) hands each scraper the set of
URLs already in `documents` for its source, so it skips re-fetching them - a fast pass
that only pulls in genuinely new pages. The trade-off: an edit to a page already
stored (same URL, changed content) is not noticed until the next full run, so alternate
it with plain full runs.

Unless `?refresh_seed=false` is passed, a run that indexes anything then rewrites the
bundled seed (`backend/seed/documents.json.gz`) from the full `documents` table, so a
fresh clone's `python -m backend.scripts.seed` starts from current content. The file
only changes on the machine running this backend - commit it to share the refresh
(same effect as running `python -m backend.scripts.export_seed` by hand). The
scheduler's own runs never touch the seed.

Each scraper in `registry.py` is tagged `frequent` or `slow`, and the two run on
separate scheduler intervals (`SCHEDULER_INTERVAL_MINUTES` and
`SCHEDULER_SLOW_INTERVAL_MINUTES`, once `ENABLE_SCHEDULER=true`) instead of together:

- **frequent** - announcements, events/projects/jobs, and the JSON feeds (courses,
  staff, theses). A handful of requests total; seconds to low minutes. These are also
  the time-sensitive ones, so they run hourly by default.
- **slow** - official course syllabi, professor profiles, info pages, linked PDFs,
  consultations, exam-session spreadsheets, and community recordings pages. None of
  these have a bulk endpoint, so it's one HTTP request per item -
  100+ requests at the deliberate 1 request/second rate limit against finki.ukim.mk
  and finki-hub.com (polite scraping, not something worth "fixing" by speeding up).
  Several minutes per pass, but this content rarely changes day to day, so it defaults
  to a weekly cadence instead of hourly.

A full reindex (no `cadence`, or the CLI script with no argument) runs both and takes
as long as the slow pass does - unless `--incremental` / `incremental=true` is set,
which skips every already-indexed URL and so finishes in seconds when little is new.
None of this is something a site visitor ever waits through either way - `/search`,
`/chat`, and the MCP tools only ever read whatever's already indexed, regardless of
what's running in the background.

## The seed (`seed/documents.json.gz`)

A committed, gzipped JSON snapshot of the `documents` table - title/url/content/metadata for
everything that was indexed at export time, plus each document's chunks and their
vectors (float16, base64). Embedding everything from scratch takes ~45+ minutes on a
CPU (mostly the ~4000 theses), so the vectors are shipped instead. They're tagged
with the embedding model's name; if `EMBEDDING_MODEL_NAME` differs, `seed.py`
ignores them and re-embeds.

- `python -m backend.scripts.seed` loads it: upserts every document and stores the
  shipped chunks, no network calls to finki.ukim.mk/finki-hub.com at all. This is how
  a new machine should bootstrap instead of waiting on a live scrape.
- `python -m backend.scripts.export_seed` regenerates it from whatever's currently in
  the DB. Maintainer-only, manual - run it after a full reindex and commit the
  result if you want future first-time setups to start from fresher data. It's a
  snapshot, not a sync: it will drift stale between refreshes, which is fine, since
  the seed's job is a fast bootstrap, not a freshness guarantee - live scraping
  (scheduler or manual reindex) is what keeps things current after setup.
- Both go through the same `upsert_document` path a live scrape
  does (matched by URL, unchanged content skipped), so seeding, reindexing, and
  re-seeding in any order/combination is safe and idempotent.

## Exam-session schedules

Two scrapers both produce `type=schedule` documents, deliberately - they're not
duplicates, they're two different reference sources students might search for by
different names:

- `finki_hub.sessions` (`source=finki_hub`) - `assets.finki-hub.com/sessions.json`,
  direct download links to the actual schedule spreadsheets. The files are downloaded
  and their text extracted, so exam dates can be looked up (`core/exam_schedule.py`).
  This is the primary source; prefer it.
- `official.schedule_links` (`source=official`) - the announcement board's own
  "Распоред на часови и консултации" widget, which links the same kind of SharePoint
  spreadsheet plus other reference links (e.g. the campus map) that aren't on
  finki-hub at all. Kept because it's cheap (one page, no per-item requests) and
  surfaces things finki-hub doesn't have, not because the exam-session part is
  uniquely necessary.

`official.schedule_links` only indexes the reference link (title + URL), so the
assistant can point a student to the right file; exact dates come from `finki_hub.sessions`.

## Known gaps (see `scrapers/registry.py`)

- `finki_hub.schedules` (`rasporedi.finki-hub.com`) - class/lecture timetables, a
  different thing from exam-session schedules above. Not implemented.

Registered but `enabled=False`, so `/admin/reindex` skips it instead of failing.
