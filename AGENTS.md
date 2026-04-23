## Goal
Build an internal AI System Analyst service.

## Product intent
The system must:
- ingest specifications and architecture docs
- retrieve relevant architecture context
- generate developer tasks in structured JSON
- show risks, assumptions, and open questions
- require human approval before Jira creation

## Rules
- Never invent architecture that is not present in the docs
- If context is insufficient, say so explicitly
- Prefer small, reviewable changes
- Keep all generated outputs deterministic and structured
- Use Python + FastAPI + PostgreSQL + pgvector
- Docker-first setup
- Add tests for core logic
- Do not implement automatic Jira creation without approval flow

## Output expectations
When implementing features, always include:
- purpose
- changed files
- validation steps
- remaining risks
