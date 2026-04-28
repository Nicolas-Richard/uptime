import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import pytest

from core.uptime_checks import run_http_check


class OKHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


class Error503Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503)
        self.end_headers()
        self.wfile.write(b"Service Unavailable")

    def log_message(self, format, *args):
        pass


class SlowHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(5)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def _start_server(handler_class):
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


@pytest.fixture()
def http_server():
    server, url = _start_server(OKHandler)
    yield url
    server.shutdown()


@pytest.fixture()
def http_503_server():
    server, url = _start_server(Error503Handler)
    yield url
    server.shutdown()


@pytest.fixture()
def http_slow_server():
    server, url = _start_server(SlowHandler)
    yield url
    server.shutdown()


async def test_run_http_check_up(http_server):
    status, status_code, response_time_ms, error_message = await run_http_check(http_server)
    assert status == "up"
    assert status_code == 200
    assert response_time_ms >= 0
    assert error_message is None


async def test_run_http_check_5xx(http_503_server):
    status, status_code, response_time_ms, error_message = await run_http_check(http_503_server)
    assert status == "down"
    assert status_code == 503
    assert response_time_ms >= 0
    assert error_message is None


async def test_run_http_check_timeout(http_slow_server):
    status, status_code, response_time_ms, error_message = await run_http_check(
        http_slow_server, timeout_seconds=0.5
    )
    assert status == "down"
    assert status_code is None
    assert error_message is not None


async def test_run_http_check_connection_refused():
    status, status_code, response_time_ms, error_message = await run_http_check(
        "http://127.0.0.1:1", timeout_seconds=2
    )
    assert status == "down"
    assert status_code is None
    assert error_message is not None
