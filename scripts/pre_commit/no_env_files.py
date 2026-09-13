#!/usr/bin/env python3
"""
Meridian — Pre-commit local hook: blocks .env files and hardcoded secrets.

Scans staged files for:
- Any file matching .env* or *.env (except .env.example)
- Files containing hardcoded secret patterns (GITHUB_PRIVATE_KEY,
  DATABASE_URL with creds, KMS_MASTER_KEY, etc.)

Usage: run automatically by pre-commit framework.
See docs/DEVELOPER_STANDARDS.md §7 and docs/SECURITY.md §2.1.
"""

import fnmatch
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Patterns that are NEVER allowed in committed files
BLOCKED_FILENAME_PATTERNS = [
    ".env*",
    "*.env",
    ".envrc",
    ".env.local",
    ".env.production",
    ".env.development",
]

# Files that are explicitly allowed despite matching above
ALLOWED_FILENAMES = {".env.example"}

# Secret patterns that block a commit if found in any file content
SECRET_PATTERNS = [
    re.compile(r"GITHUB_PRIVATE_KEY\s*=\s*['\"]?(?!your-|placeholder|dummy|example|fake)[^\s'\"]+"),
    re.compile(r"DATABASE_URL\s*=\s*.+://[^:]+:[^@]+@"),  # Contains password in URL
    re.compile(r"KMS_MASTER_KEY\s*=\s*['\"]?(?!your-|placeholder|dummy|example|fake)[^\s'\"]+"),
    re.compile(
        r"GITHUB_WEBHOOK_SECRET\s*=\s*['\"]?(?!your-|placeholder|dummy|example|fake)[^\s'\"]+"
    ),
    re.compile(
        r"AWS_SECRET_ACCESS_KEY\s*=\s*['\"]?(?!your-|placeholder|dummy|example|fake)[^\s'\"]+"
    ),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI-style API key
]

# Files to skip (they're allowed to contain placeholder patterns)
SKIP_FILES = {
    ".env.example",
    ".pre-commit-config.yaml",
    "docs/SECURITY.md",
    "docs/DEVELOPER_STANDARDS.md",
    "docs/SETUP.md",
    "scripts/pre_commit/no_env_files.py",
}


def is_blocked_filename(filepath: Path) -> bool:
    name = filepath.name
    if name in ALLOWED_FILENAMES:
        return False
    return any(fnmatch.fnmatch(name, pattern) for pattern in BLOCKED_FILENAME_PATTERNS)


def scan_file_for_secrets(filepath: Path) -> list[str]:
    issues = []
    relative = filepath.relative_to(REPO_ROOT).as_posix()
    if relative in SKIP_FILES:
        return issues
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return issues
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            issues.append(
                f"  {relative}:{line_num} — matched secret pattern: {pattern.pattern[:40]}..."
            )
    return issues


def main() -> int:
    issues: list[str] = []

    # Scan staged + unstaged files
    for filepath in REPO_ROOT.rglob("*"):
        if not filepath.is_file():
            continue
        # Skip .git, venvs, caches
        if ".git" in filepath.parts or ".venv" in filepath.parts or "__pycache__" in filepath.parts:
            continue

        if is_blocked_filename(filepath):
            issues.append(f"  Blocked filename: {filepath.relative_to(REPO_ROOT).as_posix()}")

        issues.extend(scan_file_for_secrets(filepath))

    if issues:
        print("[no_env_files] BLOCKED — found .env files or hardcoded secrets:")
        for issue in issues:
            print(issue)
        print("\nRemediation:")
        print("  1. Remove the file from git:  git rm --cached <file>")
        print("  2. Add it to .gitignore if needed")
        print("  3. Use .env.example (with placeholder values only) as the template")
        print("  4. Re-commit after fixing")
        return 1

    print("[no_env_files] OK — no .env files or hardcoded secrets found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
