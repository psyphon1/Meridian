"""Identity models — users, api_keys, installations (Task 5)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.models.base import Base, CreatedAtMixin, InstallationStatus, TimestampMixin


class User(Base, TimestampMixin):
    """A GitHub user known to Meridian."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)


class APIKey(Base, CreatedAtMixin):
    """BYOK encrypted API key (SECURITY.md §3)."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rotated_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Installation(Base, TimestampMixin):
    """A GitHub App installation."""

    __tablename__ = "installations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    github_installation_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InstallationStatus.ACTIVE)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
