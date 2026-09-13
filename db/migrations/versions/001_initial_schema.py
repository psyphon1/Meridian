"""Initial Meridian schema — all 14 tables, indexes, audit sequence.

Revision ID: 001
Revises:
Create Date: 2026-09-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- identity (users) ---
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_id"),
    )

    # --- identity (api_keys) ---
    op.create_table(
        "api_keys",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider"),
    )

    # --- identity (installations) ---
    op.create_table(
        "installations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("github_installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_installation_id"),
    )
    op.create_index("ix_installations_status", "installations", ["status"])

    # --- repository (repositories) ---
    op.create_table(
        "repositories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "installation_id", sa.BigInteger(), sa.ForeignKey("installations.id"), nullable=False
        ),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(512), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_repo_id"),
    )
    op.create_index("ix_repositories_installation", "repositories", ["installation_id"])

    # --- repository (commits) ---
    op.create_table(
        "commits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "repository_id", sa.BigInteger(), sa.ForeignKey("repositories.id"), nullable=False
        ),
        sa.Column("sha", sa.String(40), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("authored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commits_repo_sha", "commits", ["repository_id", "sha"], unique=True)

    # --- repository (files) ---
    op.create_table(
        "files",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "repository_id", sa.BigInteger(), sa.ForeignKey("repositories.id"), nullable=False
        ),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("last_commit_sha", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_files_repo_path", "files", ["repository_id", "path"], unique=True)

    # --- repository (code_symbols) ---
    op.create_table(
        "code_symbols",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.BigInteger(), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_code_symbols_file", "code_symbols", ["file_id"])

    # --- review (pull_requests) ---
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "repository_id", sa.BigInteger(), sa.ForeignKey("repositories.id"), nullable=False
        ),
        sa.Column("github_pr_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("head_sha", sa.String(40), nullable=False),
        sa.Column("base_sha", sa.String(40), nullable=False),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "github_pr_number", name="uq_pr_repo_number"),
    )
    op.create_index("ix_pull_requests_state", "pull_requests", ["state"])

    # --- review (review_runs) ---
    op.create_table(
        "review_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "pull_request_id", sa.BigInteger(), sa.ForeignKey("pull_requests.id"), nullable=False
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="RECEIVED"),
        sa.Column("risk_tier", sa.String(10), nullable=True, server_default="MEDIUM"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_runs_status", "review_runs", ["status"])

    # --- review (evidence) ---
    op.create_table(
        "evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "review_run_id", sa.BigInteger(), sa.ForeignKey("review_runs.id"), nullable=False
        ),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("artifact_ref", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # --- review (findings) ---
    op.create_table(
        "findings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "review_run_id", sa.BigInteger(), sa.ForeignKey("review_runs.id"), nullable=False
        ),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="MEDIUM"),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.BigInteger(), sa.ForeignKey("evidence.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_run_severity", "findings", ["review_run_id", "severity"])

    # --- review (tool_runs) ---
    op.create_table(
        "tool_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "review_run_id", sa.BigInteger(), sa.ForeignKey("review_runs.id"), nullable=False
        ),
        sa.Column("tool_name", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("output_ref", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_runs_run", "tool_runs", ["review_run_id"])

    # --- review (review_memory) ---
    op.create_table(
        "review_memory",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "repository_id", sa.BigInteger(), sa.ForeignKey("repositories.id"), nullable=False
        ),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "key", name="uq_review_memory_repo_key"),
    )

    # --- audit (audit_events, hash-chained) ---
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sequence_number"),
    )
    op.create_index("ix_audit_events_type", "audit_events", ["event_type"])
    op.execute("CREATE SEQUENCE IF NOT EXISTS audit_events_seq")

    # --- audit (webhook_deliveries: idempotency + transactional outbox) ---
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("delivery_id", sa.String(255), nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_size_bytes", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enqueued", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id"),
    )
    op.create_index("ix_webhook_deliveries_enqueued", "webhook_deliveries", ["enqueued"])


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS audit_events_seq")
    op.drop_table("webhook_deliveries")
    op.drop_table("audit_events")
    op.drop_table("review_memory")
    op.drop_table("tool_runs")
    op.drop_table("findings")
    op.drop_table("evidence")
    op.drop_table("review_runs")
    op.drop_table("pull_requests")
    op.drop_table("code_symbols")
    op.drop_table("files")
    op.drop_table("commits")
    op.drop_table("repositories")
    op.drop_table("installations")
    op.drop_table("api_keys")
    op.drop_table("users")
