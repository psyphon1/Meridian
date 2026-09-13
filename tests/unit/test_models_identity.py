from sqlalchemy import inspect as sa_inspect

from packages.models.identity import APIKey, Installation, User


def test_user_table_columns():
    cols = {c.name for c in sa_inspect(User).columns}
    assert cols == {
        "id",
        "github_id",
        "username",
        "email",
        "avatar_url",
        "created_at",
        "updated_at",
    }


def test_api_key_table_columns():
    cols = {c.name for c in sa_inspect(APIKey).columns}
    assert cols == {"id", "user_id", "provider", "encrypted_key", "is_active", "created_at", "rotated_at"}


def test_installation_table_columns():
    cols = {c.name for c in sa_inspect(Installation).columns}
    assert cols == {
        "id",
        "github_installation_id",
        "account_login",
        "account_type",
        "status",
        "user_id",
        "created_at",
        "updated_at",
    }


def test_installation_github_id_unique():
    col = sa_inspect(Installation).columns["github_installation_id"]
    assert col.unique is True
