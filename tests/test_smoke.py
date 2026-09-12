"""Repository placement smoke tests.

Verifies the repo-wide Python contract before Phase 1 source lands:
- interpreter is Python 3.12+ (docs/SETUP.md, pyproject.toml `requires-python`).
- the declared dependency contract is loadable from pyproject.toml.

These are replaced by real unit/integration coverage as `apps/`, `packages/`,
and `services/` are implemented. Keeping them green is enough to prove the
toolchain (pytest / CI) is wired correctly today.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_python_version_is_supported() -> None:
    assert sys.version_info >= (3, 12), f"Meridian requires Python 3.12+, got {sys.version}"


def test_requires_python_declares_312_floor() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires = data["project"]["requires-python"]
    assert "3.12" in requires, f"pyproject.toml should require >=3.12, got {requires!r}"


def test_core_dependency_contract_is_declared() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = data["project"]["dependencies"]
    names = [d.split(">=")[0].split(" <")[0].split("[")[0] for d in deps]
    for required in ("fastapi", "langgraph", "litellm", "sqlalchemy", "redis"):
        assert required in names, f"Expected runtime dependency {required!r}"


def test_dev_extra_declares_quality_tooling() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = data["project"]["optional-dependencies"]["dev"]
    combined = " ".join(dev)
    for tool in ("pytest", "ruff", "mypy"):
        assert tool in combined, f"Expected dev tooling {tool!r}"
