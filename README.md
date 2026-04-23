# AI System Analyst MVP

Internal service for ingesting specifications and architecture documents, retrieving grounded architecture context, and producing reviewable implementation tasks before any Jira export.

## What works in Milestone 2

- FastAPI backend scaffold
- PostgreSQL + pgvector data model and Alembic migrations
- Local file storage for uploaded documents
- Text document ingestion with chunking and metadata
- PostgreSQL-backed retrieval service with:
  - document filtering by kind, explicit document IDs, and metadata
  - chunk text search with deterministic ranking
- Analysis run persistence in `analysis_runs`
- Analysis run API endpoints:
  - `POST /api/v1/analysis-runs`
  - `GET /api/v1/analysis-runs/{analysis_run_id}`
- Deterministic analysis output that returns the strict JSON contract and preserves:
  - `source_references`
  - task-level `source_refs`
  - confidence values
  - explicit `open_questions` and `assumptions` when context is thin
- Jira export stub endpoint that is disabled by default
- Targeted tests for retrieval, upload, and analysis run APIs

## Still pending or intentionally stubbed

- Extraction currently supports plain text style files (`.txt`, `.md`)
- Embedding generation is not wired yet, so pgvector similarity remains inactive scaffolding
- Retrieval currently uses deterministic text ranking rather than embedding similarity
- Analysis generation is deterministic and rule-based for now; no heavy LLM integration is active
- Jira export remains a manual approval stub only
- PDF and DOCX ingestion are intentionally out of scope for this milestone

## Local run

1. Copy `.env.example` to `.env`
2. Start services:

```bash
docker compose up --build
```

3. Run migrations in another shell:

```bash
docker compose exec api alembic upgrade head
```

4. Open the API docs at `http://localhost:8000/docs`

## Main API flow now

1. Upload a document with `POST /api/v1/documents/upload`
2. Inspect stored documents with `GET /api/v1/documents`
3. Start an analysis run with `POST /api/v1/analysis-runs`
4. Retrieve a stored run with `GET /api/v1/analysis-runs/{analysis_run_id}`
5. See Jira export safety stub with `POST /api/v1/exports/jira`

### Example analysis request

```json
{
  "query": "Implement retrieval-backed analysis runs",
  "document_ids": ["<document-uuid>"],
  "document_kind": "specification",
  "metadata_filters": {
    "extension": ".md"
  },
  "max_chunks": 6
}
```

### Analysis response notes

- The response includes the required analysis contract fields at the top level:
  - `feature_summary`
  - `affected_components`
  - `backend_tasks`
  - `frontend_tasks`
  - `integration_tasks`
  - `db_changes`
  - `qa_tasks`
  - `observability_tasks`
  - `risks`
  - `open_questions`
  - `assumptions`
  - `source_references`
  - `confidence`
- Run metadata such as `id`, `status`, `document_id`, `request_payload`, `validation_notes`, and `created_at` is returned alongside the contract.

## Local development without Docker

1. Create a virtual environment
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Set environment variables from `.env.example`
4. Run the API:

```bash
uvicorn app.main:app --reload
```

5. Run tests:

```bash
pytest
```

## Alternative local verification

If the local Python environment cannot see `pytest` after install, use a repository-local package directory:

```powershell
python -m pip install --upgrade pip
New-Item -ItemType Directory -Force .tmp, .pytest-packages | Out-Null
$env:TEMP = (Resolve-Path .tmp)
$env:TMP = (Resolve-Path .tmp)
python -m pip install --target .pytest-packages pytest
$env:PYTHONPATH = "$(Resolve-Path .pytest-packages);$(Get-Location)"
python -c "from _pytest.config import console_main; raise SystemExit(console_main())" tests
```

This keeps the existing `app/` layout intact while avoiding user-site and broken virtualenv issues that showed up in this environment.

## VPS notes

- Install Docker Engine and Docker Compose plugin
- Copy `.env.example` to `.env` and update secrets
- Run `docker compose up --build -d`
- Run `docker compose exec api alembic upgrade head`
- Mount a persistent volume for `./storage`

## Retrieval and analysis notes

- Retrieval is database-backed and works today with document metadata filters plus deterministic text ranking.
- pgvector remains part of the schema, but vector search is explicitly disabled until embedding generation is implemented safely.
- Analysis outputs are grounded only in retrieved chunk text and always keep explicit source references.
