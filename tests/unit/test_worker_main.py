"""Unit tests for the worker main entry point (Task 26)."""

import socket

from apps.worker.main import make_consumer_name


def test_consumer_name_format():
    name = make_consumer_name()
    assert isinstance(name, str)
    assert len(name) > 0
    # Should contain hostname + pid components
    assert socket.gethostname().split(".")[0] in name or "-" in name
