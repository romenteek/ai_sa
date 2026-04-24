# AI System Analyst MVP

Internal service for ingesting specifications and architecture documents, retrieving grounded architecture context, producing reviewable implementation tasks, and preparing explicitly gated Jira exports after human approval.

## What works in Milestone 4

- FastAPI backend scaffold with server-rendered internal UI
- PostgreSQL + pgvector data model and Alembic migrations
- Local file storage for uploaded documents
- Text document ingestion with chunking and metadata
- PostgreSQL-backed retrieval with deterministic text ranking
- Persisted analysis runs and persisted review workflow
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
  - document upload/list/detail at `/documents`
  - analysis creation at `/analysis-runs/new`
  - analysis run queue at `/analysis-runs`
  - full structured review page at `/analysis-runs/{analysis_run_id}`
  - Jira export preview at `/analysis-runs/{analysis_run_id}/export`
- Manual Jira export flow with explicit preview and confirmation
- Approval-gated export behavior:
  - non-approved runs can be previewed but cannot be exported
  - only approved runs can proceed to export confirmation
- Dry-run/manual-preview export mode when Jira is not fully configured

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
- Embedding generation is not wired yet, so pgvector similarity remains inactive scaffolding
- Retrieval still uses deterministic text ranking rather than embeddings
- Analysis generation remains deterministic and rule-based
- Automatic Jira creation is intentionally not implemented
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

1. Upload a document in `/documents`
2. Start an analysis run in `/analysis-runs/new`
3. Review the full structured result in `/analysis-runs/{analysis_run_id}`
4. Update review status and reviewer note
5. Open the Jira export preview from the analysis run detail page
6. Confirm the export explicitly
7. If Jira is not fully configured, inspect the dry-run payload and use it manually

## Main API flow

1. Upload a document with `POST /api/v1/documents/upload`
2. Start an analysis run with `POST /api/v1/analysis-runs`
3. Review or update approval state with `PATCH /api/v1/analysis-runs/{analysis_run_id}/review`
4. Build the export preview with `POST /api/v1/exports/jira/preview`
5. Confirm the export with `POST /api/v1/exports/jira`

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

## Retrieval, review, and export notes

- Retrieval is database-backed and grounded only in stored chunk text
- Source references and confidence are preserved through review and export preview
- Export preview is intentionally human-readable before any confirmation step
- Export confirmation stays dry-run until Jira credentials and enablement are configured explicitly
