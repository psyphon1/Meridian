ALLOWED_EVENTS: dict[str, set[str]] = {
    "pull_request": {"opened", "synchronize", "reopened", "edited"},
    "installation": {"created", "deleted", "new_permissions_accepted"},
    "installation_repositories": {"added", "removed"},
}


def is_event_allowed(event: str, action: str) -> bool:
    """Check whether an event/action pair is in the allowed set."""
    return action in ALLOWED_EVENTS.get(event, set())
