# ai_sa

Minimal repository bootstrap for reliable local verification.

## Local setup

Install the test dependency into a repository-local directory:

```powershell
python -m pip install --upgrade pip
New-Item -ItemType Directory -Force .tmp, .pytest-packages | Out-Null
$env:TEMP = (Resolve-Path .tmp)
$env:TMP = (Resolve-Path .tmp)
python -m pip install --target .pytest-packages pytest
```

## Verification

Run these commands from the repository root:

```powershell
python -m compileall src tests
python scripts/run_pytest.py
```

Why this workflow is reliable:

- `compileall` checks Python syntax in the package and tests.
- `scripts/run_pytest.py` adds the repository `src/` directory to `sys.path`, so tests do not depend on the current working directory.
- `python -m pip install --target .pytest-packages pytest` keeps the test dependency inside the repository, which avoids user-site and virtualenv inconsistencies in this environment.

## Environment note

In this Codex execution environment, `python -m venv .venv` failed during `ensurepip`, and `pip install -e .[dev]` did not produce an importable `pytest` for the active interpreter. Those limitations appear to be environment-specific rather than repository-specific. The repository-local verification commands above avoid both issues.

## Current repository scope

The canonical remote currently contains only `AGENTS.md` plus this verification bootstrap. Product features, retrieval work, and analysis API expansion are intentionally out of scope for this turn.
