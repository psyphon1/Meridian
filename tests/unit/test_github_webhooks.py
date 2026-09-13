from packages.github.webhooks import ALLOWED_EVENTS, is_event_allowed


def test_pull_request_opened_allowed():
    assert is_event_allowed("pull_request", "opened") is True


def test_pull_request_closed_not_allowed():
    assert is_event_allowed("pull_request", "closed") is False


def test_installation_created_allowed():
    assert is_event_allowed("installation", "created") is True


def test_installation_repositories_added_allowed():
    assert is_event_allowed("installation_repositories", "added") is True


def test_unknown_event_not_allowed():
    assert is_event_allowed("push", "anything") is False


def test_allowed_events_complete():
    assert "pull_request" in ALLOWED_EVENTS
    assert ALLOWED_EVENTS["pull_request"] == {"opened", "synchronize", "reopened", "edited"}
    assert ALLOWED_EVENTS["installation"] == {"created", "deleted", "new_permissions_accepted"}
    assert ALLOWED_EVENTS["installation_repositories"] == {"added", "removed"}
