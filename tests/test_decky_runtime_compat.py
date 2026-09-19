from pathlib import Path
import socket

from decky_http_server import SOCKET_BUFFER_BYTES, _SocketWriter


ROOT = Path(__file__).resolve().parents[1]


def test_backend_uses_bundled_http_compatibility_layer():
    source = (ROOT / "core_main.py").read_text(encoding="utf-8")
    assert "from decky_http_server import BaseHTTPRequestHandler, ThreadingHTTPServer" in source
    assert "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer" not in source


def test_startup_avoids_blocking_hostname_lookup():
    source = (ROOT / "core_main.py").read_text(encoding="utf-8")
    assert "socket.getaddrinfo(socket.gethostname()" not in source


def test_server_startup_is_guarded_and_time_bounded():
    source = (ROOT / "core_main.py").read_text(encoding="utf-8")
    assert "_START_SERVER_LOCK = threading.Lock()" in source
    assert "await asyncio.wait_for(asyncio.to_thread(start_server), timeout=4.0)" in source


def test_socket_writer_uses_full_send_contract():
    left, right = socket.socketpair()
    try:
        writer = _SocketWriter(left)
        payload = b"DeckyShare" * 4096
        assert writer.write(payload) == len(payload)
        received = bytearray()
        while len(received) < len(payload):
            received.extend(right.recv(len(payload) - len(received)))
        assert bytes(received) == payload
    finally:
        left.close()
        right.close()


def test_transfer_socket_buffer_is_large_enough_for_bulk_files():
    assert SOCKET_BUFFER_BYTES >= 4 * 1024 * 1024
