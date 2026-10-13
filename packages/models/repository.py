"""Repository-scoped models — repositories, commits, files, code_symbols (Task 6)."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from packages.models.base import Base, CreatedAtMixin, TimestampMixin


class Repository(Base, TimestampMixin):
    """A repository accessible via an installation."""

    __tablename__ = "repositories"
    __table_args__ = (Index("ix_repositories_installation", "installation_id"),)

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
    __table_args__ = (Index("ix_commits_repo_sha", "repository_id", "sha", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("repositories.id"), nullable=False
    )
    sha: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class File(Base, TimestampMixin):
    """A tracked file in a repository (code intelligence index)."""

    __tablename__ = "files"
    __table_args__ = (Index("ix_files_repo_path", "repository_id", "path", unique=True),)

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

    embedding: pgvector ``vector(1536)`` (ADR-002, spec §5.1); nullable until the
    embedding pipeline lands (Phase 2). The HNSW index is also Phase 2.
    """

    __tablename__ = "code_symbols"
    __table_args__ = (Index("ix_code_symbols_file", "file_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("files.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
