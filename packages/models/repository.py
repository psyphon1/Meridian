"""Repository-scoped models — repositories, commits, files, code_symbols (Task 6)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.models.base import Base, CreatedAtMixin, TimestampMixin


class Repository(Base, TimestampMixin):
    """A repository accessible via an installation."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    installation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("installations.id"), nullable=False
    )
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)


class Commit(Base, CreatedAtMixin):
    """A commit on a repository."""

    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False
    )
    sha: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authored_at: Mapped[datetime | None] = mapped_column(nullable=True)


class File(Base, TimestampMixin):
    """A tracked file in a repository (code intelligence index)."""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)


class CodeSymbol(Base, CreatedAtMixin):
    """A symbol extracted from a file (code intelligence index).

    embedding: pgvector(1536) — declared in the Alembic migration (Task 10)
    as ARRAY(Float) placeholder; replaced with vector(1536) in Phase 2.
    """

    __tablename__ = "code_symbols"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("files.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
