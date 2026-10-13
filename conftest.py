"""Root conftest — import path + shared test fixtures (pytest 8 requires
pytest_plugins to be declared in the root conftest)."""

import asyncio
import sys
from pathlib import Path

# psycopg async requires SelectorEventLoop on Windows (Proactor is the default).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).resolve().parent))

pytest_plugins = ["tests.fixtures.db", "tests.fixtures.redis"]
