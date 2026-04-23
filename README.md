# AI System Analyst MVP

Internal service for ingesting specifications and architecture documents, retrieving grounded architecture context, and producing reviewable implementation tasks before any Jira export.

## What is implemented in this first pass

- FastAPI backend scaffold
- PostgreSQL + pgvector data model and Alembic migration
- Local file storage for uploaded documents
- Text document ingestion with chunking and metadata
- Basic review-oriented document APIs
- Jira export stub endpoint that is disabled by default
- Core tests for chunking and upload flow

## Current limitations

- Extraction currently supports plain text style files (`.txt`, `.md`)
- Embedding generation and vector retrieval are scaffolded but not yet active
- Analysis generation and review workflow are partially scaffolded and will be expanded in later milestones

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

## VPS notes

- Install Docker Engine and Docker Compose plugin
- Copy `.env.example` to `.env` and update secrets
- Run `docker compose up --build -d`
- Run `docker compose exec api alembic upgrade head`
- Mount a persistent volume for `./storage`

## Main API flow today

1. Upload a document with `POST /api/v1/documents/upload`
2. Inspect stored documents with `GET /api/v1/documents`
3. Review chunks with `GET /api/v1/documents/{document_id}`
4. See Jira export safety stub with `POST /api/v1/exports/jira`
