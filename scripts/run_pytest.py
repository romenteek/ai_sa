"""Run pytest using repository-local dependencies and package source."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / ".pytest-packages"))
    sys.path.insert(0, str(repo_root / "src"))

    try:
        import pytest
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "pytest is not installed. Run `python -m pip install --target .pytest-packages pytest` first."
        ) from exc

    return pytest.main(["tests"])


if __name__ == "__main__":
    raise SystemExit(main())
