"""Root conftest — ensures the worktree root is importable as `packages`/`apps`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
