"""Typed models for GitHub REST API requests/responses used by the client (spec §6.4)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InstallationToken(BaseModel):
    """Response of ``POST /app/installations/{id}/access_tokens`` (only fields we use)."""

    token: str = Field(repr=False)  # secret — keep out of reprs/logs
    expires_at: datetime


class PRFile(BaseModel):
    """One entry of ``GET /repos/{owner}/{repo}/pulls/{n}/files``."""

    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    sha: str | None = None
    patch: str | None = None  # absent for binary / very large diffs
    previous_filename: str | None = None


class ReviewComment(BaseModel):
    """An inline review comment (``comments[]`` of a create-review request)."""

    path: str
    body: str
    line: int | None = None
    side: Literal["LEFT", "RIGHT"] = "RIGHT"
    start_line: int | None = None
    start_side: Literal["LEFT", "RIGHT"] | None = None


class ReviewPayload(BaseModel):
    """Body of ``POST /repos/{owner}/{repo}/pulls/{n}/reviews``.

    ``event`` deliberately excludes ``APPROVE``: Meridian escalates to humans and
    never approves/merges (README principle 5, AGENTS.md).
    """

    body: str = ""
    event: Literal["COMMENT", "REQUEST_CHANGES"] = "COMMENT"
    commit_id: str | None = None  # pin the review to the reviewed head SHA
    comments: list[ReviewComment] = Field(default_factory=list)
