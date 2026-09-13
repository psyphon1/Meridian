from packages.models.review import Evidence, Finding, PullRequest, ReviewMemory, ReviewRun, ToolRun
from sqlalchemy import inspect as sa_inspect


def test_pull_request_columns():
    cols = {c.name for c in sa_inspect(PullRequest).columns}
    assert cols == {
        "id",
        "repository_id",
        "github_pr_number",
        "title",
        "body",
        "head_sha",
        "base_sha",
        "author",
        "state",
        "created_at",
        "updated_at",
    }


def test_review_run_columns():
    cols = {c.name for c in sa_inspect(ReviewRun).columns}
    assert cols == {
        "id",
        "pull_request_id",
        "status",
        "risk_tier",
        "started_at",
        "completed_at",
        "error_message",
        "created_at",
        "updated_at",
    }


def test_finding_columns():
    cols = {c.name for c in sa_inspect(Finding).columns}
    assert cols == {
        "id",
        "review_run_id",
        "category",
        "severity",
        "confidence",
        "file_path",
        "start_line",
        "end_line",
        "message",
        "evidence_id",
        "created_at",
    }


def test_evidence_columns():
    cols = {c.name for c in sa_inspect(Evidence).columns}
    assert cols == {
        "id",
        "review_run_id",
        "type",
        "artifact_ref",
        "summary",
        "verified",
        "created_at",
    }


def test_tool_run_columns():
    cols = {c.name for c in sa_inspect(ToolRun).columns}
    assert cols == {
        "id",
        "review_run_id",
        "tool_name",
        "status",
        "output_ref",
        "duration_ms",
        "created_at",
    }


def test_review_memory_columns():
    cols = {c.name for c in sa_inspect(ReviewMemory).columns}
    assert cols == {"id", "repository_id", "key", "value", "created_at", "updated_at"}


def test_pr_unique_repo_number():
    uqs = PullRequest.__table__.constraints
    unique_pairs = {
        tuple(c.name for c in uc.columns)
        for uc in uqs
        if uc.__class__.__name__ == "UniqueConstraint"
    }
    assert ("repository_id", "github_pr_number") in unique_pairs
