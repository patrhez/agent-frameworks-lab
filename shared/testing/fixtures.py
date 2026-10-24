"""Default tests cannot open HTTP/TCP connections, including accidental client use."""
import os
import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    if os.getenv("RUN_LIVE") == "1":
        return
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError("Network connections are forbidden in default mock tests")
        return original(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError("Network connections are forbidden in default mock tests")
        return original_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
