"""Run pytest using repository-local dependencies and repository source."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / ".pytest-packages"))
    sys.path.insert(0, str(repo_root))

    try:
        import pytest
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "pytest is not installed. Run `python -m pip install --target .pytest-packages pytest` first."
        ) from exc

    if hasattr(pytest, "main"):
        return pytest.main(["tests"])

    try:
        from _pytest.config import main as pytest_main
    except ModuleNotFoundError as exc:
        raise SystemExit("pytest import succeeded, but no runnable entrypoint was available.") from exc

    return pytest_main(["tests"])


if __name__ == "__main__":
    raise SystemExit(main())
