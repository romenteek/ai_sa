# AI System Analyst MVP

Internal service for ingesting specifications and architecture documents, retrieving grounded architecture context, producing reviewable implementation tasks, and preparing explicitly gated Jira exports after human approval.

## What works in Milestone 6

- FastAPI backend scaffold with server-rendered internal UI
- PostgreSQL + pgvector data model and Alembic migrations
- Local file storage for uploaded documents
- Practical bilingual RU/EN UI support with a visible language switcher
- UI language persistence through the `ui_lang` cookie, with `?lang=ru` or `?lang=en` overrides
- Project records with source type, repository URL, or uploaded archive reference
- Text document ingestion with chunking and metadata
- PostgreSQL-backed retrieval with deterministic text ranking
- Project-aware analysis requests with required task type:
  - `feature`
  - `enhancement`
  - `bug`
  - `technical_task`
  - `spike`
- Initial analysis can stop for clarification instead of forcing final implementation output
- Multiple clarification rounds with persisted AI questions and user answers
- Heuristic language detection for request text, clarification answers, and retrieved document text
- Clarification questions and deterministic final output prefer the request language or selected UI language
- Dedicated final Results section for completed analyses
- Persisted review workflow for completed outputs
- Review statuses on analysis runs:
  - `draft`
  - `reviewed`
  - `approved`
  - `rejected`
- Reviewer note storage on analysis runs
- Deterministic structured analysis output that preserves:
  - `source_references`
  - task-level `source_refs`
  - confidence values
  - explicit `open_questions`
  - explicit `assumptions`
- Internal UI pages for:
  - dashboard at `/`
  - project create/list/detail at `/projects`
  - document upload/list/detail at `/documents`
  - analysis creation at `/analysis-runs/new`
  - clarification queue at `/clarifications`
  - completed results at `/results`
  - full structured review page at `/analysis-runs/{analysis_run_id}`
  - Jira export preview at `/analysis-runs/{analysis_run_id}/export`
- Manual Jira export flow with explicit preview and confirmation
- Approval-gated export behavior:
  - non-approved runs can be previewed but cannot be exported
  - only approved runs can proceed to export confirmation
- Dry-run/manual-preview export mode when Jira is not fully configured
- Refreshed internal UI with cleaner layout, modern typography, stronger focus states, clearer cards, tables, forms, and status badges

## Language behavior

- Switch the UI language with the RU / EN selector in the sidebar.
- Direct links also work:
  - Russian UI: `http://127.0.0.1:8000/projects?lang=ru`
  - English UI: `http://127.0.0.1:8000/projects?lang=en`
- The selected language is stored in a `ui_lang` cookie.
- UI labels, navigation, form labels, page titles, major empty states, status badges, and key workflow text are translated.
- API analysis requests can optionally pass `"language": "ru"` or `"language": "en"`.
- If no language is provided, the service uses a lightweight heuristic:
  - Cyrillic-heavy request, answer, or document text is treated as Russian.
  - Otherwise the workflow defaults to English.
- The heuristic is intentionally simple and deterministic. Mixed-language requests are supported, but the output language is a best practical guess rather than full NLP detection.

## Export behavior in this milestone

- `POST /api/v1/exports/jira/preview` builds the Jira-ready payload preview
- `POST /api/v1/exports/jira` requires explicit `confirm=true`
- Export preview shows:
  - project key
  - issue type
  - summary
  - description
  - acceptance criteria
  - assumptions
  - open questions
  - source references
  - confidence
  - review status
  - reviewer note
- If Jira is not fully configured, confirmation returns a dry-run result instead of writing externally
- Live Jira writes are attempted only when all of these are configured:
  - `JIRA_EXPORT_ENABLED=true`
  - `JIRA_BASE_URL`
  - `JIRA_USER_EMAIL`
  - `JIRA_API_TOKEN`

## Still pending or intentionally stubbed

- Extraction currently supports only `.txt` and `.md`
- Project GitHub clone/archive indexing is not implemented yet; this milestone records the source and leaves an explicit ingestion boundary
- Embedding generation is not wired yet, so pgvector similarity remains inactive scaffolding
- Retrieval still uses deterministic text ranking rather than embeddings
- Analysis generation remains deterministic and rule-based
- Language detection is heuristic and does not translate arbitrary source documents; it localizes deterministic workflow text and keeps quoted source text as uploaded
- Automatic Jira creation is intentionally not implemented
- Jira field mapping expansion is intentionally deferred
- PDF and DOCX ingestion remain out of scope

## Canonical local run

Canonical browser URL:
- `http://127.0.0.1:8000`

Recommended start path:

1. Copy `.env.example` to `.env`
2. Start everything:

```bash
docker compose up --build
```

3. Open:

```text
http://127.0.0.1:8000
```

Notes:
- The `api` container now runs `alembic upgrade head` before starting Uvicorn
- You do not need a separate migration command for the normal Docker flow
- Docker uses the `.env` example defaults, including `APP_HOST=0.0.0.0`

## Local Python run path

Use this when you already have a reachable PostgreSQL database and want to run without Docker.

1. Install dependencies:

```bash
pip install -e .[dev]
```

2. Set environment variables:

- `DATABASE_URL` should point to your local PostgreSQL instance, for example:

```text
postgresql+psycopg://postgres:postgres@localhost:5432/ai_sa
```

- Set a browser-friendly host:

```text
APP_HOST=127.0.0.1
APP_PORT=8000
```

3. Run migrations:

```bash
alembic upgrade head
```

4. Start the app:

```bash
python scripts/run_local.py
```

5. Open:

```text
http://127.0.0.1:8000
```

## Main UI flow

1. Create a project in `/projects` using a GitHub URL or uploaded archive
2. Upload supporting `.txt` or `.md` source documents in `/documents`
3. Start an analysis request in `/analysis-runs/new` and select the project and task type
4. If the request is under-specified, answer questions from `/clarifications` or the analysis detail page
5. Repeat clarification until the run reaches `completed`
6. Review completed final output in `/results`
7. Open the Jira export preview from the completed analysis detail page when appropriate
8. If Jira is not fully configured, inspect the dry-run payload and use it manually

## Main API flow

1. Create a project with `POST /api/v1/projects`
2. Upload a document with `POST /api/v1/documents/upload`
3. Start an analysis request with `POST /api/v1/analysis-runs`
4. When status is `needs_clarification`, answer with `POST /api/v1/analysis-runs/{analysis_run_id}/clarifications`
5. List completed final outputs with `GET /api/v1/analysis-runs/results`
6. Review or update approval state with `PATCH /api/v1/analysis-runs/{analysis_run_id}/review`
7. Build the export preview with `POST /api/v1/exports/jira/preview`
8. Confirm the export with `POST /api/v1/exports/jira`

### Example analysis request

```json
{
  "project_id": "<project-uuid>",
  "task_type": "feature",
  "input_type": "text",
  "input_text": "Add project-aware analysis with clarification rounds.",
  "language": "en",
  "query": "Project-aware analysis workflow",
  "document_ids": ["<document-uuid>"],
  "max_chunks": 6
}
```

Possible analysis statuses:

- `draft`
- `needs_clarification`
- `clarification_answered`
- `ready_for_final_analysis`
- `completed`

### Example Jira preview request

```json
{
  "analysis_run_id": "<analysis-run-uuid>",
  "project_key": "AISA",
  "issue_type": "Task"
}
```

### Example Jira export confirmation request

```json
{
  "analysis_run_id": "<analysis-run-uuid>",
  "project_key": "AISA",
  "issue_type": "Task",
  "confirm": true
}
```

## Environment variables

- `APP_NAME`
- `APP_ENV`
- `APP_DEBUG`
- `APP_HOST`
- `APP_PORT`
- `DATABASE_URL`
- `STORAGE_DIR`
- `MAX_CHUNK_SIZE`
- `CHUNK_OVERLAP`
- `JIRA_EXPORT_ENABLED`
- `JIRA_BASE_URL`
- `JIRA_USER_EMAIL`
- `JIRA_API_TOKEN`
- `JIRA_PROJECT_KEY`
- `JIRA_ISSUE_TYPE`

## Alternative local verification

If the local Python environment cannot see `pytest` after install, use a repository-local package directory:

```powershell
python -m pip install --upgrade pip
New-Item -ItemType Directory -Force .tmp, .pytest-packages | Out-Null
$env:TEMP = (Resolve-Path .tmp)
$env:TMP = (Resolve-Path .tmp)
python -m pip install --target .pytest-packages -e .[dev]
$env:PYTHONPATH = "$(Resolve-Path .pytest-packages);$(Get-Location)"
python -c "import pytest; raise SystemExit(pytest.main(['tests']))"
```

## Milestone 6 verification performed

Automated validation:

```powershell
$env:PYTHONPATH = ".pytest-packages;."
python -m pytest tests
```

Expected result:

```text
20 passed
```

Live UI smoke verification used a temporary SQLite database and port `8765`:

```powershell
$env:PYTHONPATH='.;.pytest-packages'
$env:DATABASE_URL='sqlite:///./smoke_m6.db'
$env:STORAGE_DIR='./smoke-storage'
$env:APP_HOST='127.0.0.1'
$env:APP_PORT='8765'
python -c "from app.db.base import Base; from app.db.session import engine; Base.metadata.create_all(bind=engine)"
python scripts/run_local.py
```

Browser URL verified:

```text
http://127.0.0.1:8765/projects?lang=ru
```

The live server returned `200`, and the in-app browser saw the Russian title `Проекты - AI Системный аналитик` with RU/EN navigation present.

## Retrieval, review, and export notes

- Retrieval is database-backed and grounded only in stored chunk text
- Source references and confidence are preserved through review and export preview
- Export preview is intentionally human-readable before any confirmation step
- Export confirmation stays dry-run until Jira credentials and enablement are configured explicitly
