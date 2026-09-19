from pathlib import Path


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
