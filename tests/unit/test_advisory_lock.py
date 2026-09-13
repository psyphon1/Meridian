from packages.security.advisory_lock import compute_lock_key


def test_compute_lock_key_returns_int():
    key = compute_lock_key(repo_id=67890, pr_number=42, head_sha="abc123def456")
    assert isinstance(key, int)
    assert -(2**63) <= key <= 2**63 - 1  # 64-bit range


def test_compute_lock_key_deterministic():
    k1 = compute_lock_key(1, 2, "sha")
    k2 = compute_lock_key(1, 2, "sha")
    assert k1 == k2


def test_compute_lock_key_different_inputs_different_keys():
    k1 = compute_lock_key(1, 2, "sha")
    k2 = compute_lock_key(2, 1, "sha")
    assert k1 != k2
