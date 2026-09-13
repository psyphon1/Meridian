from packages.models.repository import CodeSymbol, Commit, File, Repository
from sqlalchemy import inspect as sa_inspect


def test_repository_columns():
    cols = {c.name for c in sa_inspect(Repository).columns}
    assert cols == {
        "id",
        "installation_id",
        "github_repo_id",
        "owner",
        "name",
        "full_name",
        "default_branch",
        "is_private",
        "created_at",
        "updated_at",
    }


def test_commit_columns():
    cols = {c.name for c in sa_inspect(Commit).columns}
    assert cols == {"id", "repository_id", "sha", "message", "author", "authored_at", "created_at"}


def test_file_columns():
    cols = {c.name for c in sa_inspect(File).columns}
    assert cols == {
        "id",
        "repository_id",
        "path",
        "language",
        "size",
        "last_commit_sha",
        "created_at",
        "updated_at",
    }


def test_code_symbol_columns():
    cols = {c.name for c in sa_inspect(CodeSymbol).columns}
    assert cols == {
        "id",
        "file_id",
        "name",
        "kind",
        "start_line",
        "end_line",
        "signature",
        "created_at",
    }


def test_github_repo_id_unique():
    assert sa_inspect(Repository).columns["github_repo_id"].unique is True
