"""Loopback-only UI server. The browser can invoke a fixed set of device operations."""
import json
import secrets
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from .adb import PilotError
from .console import Console


class LocalServer(ThreadingHTTPServer):
    # Allow verified settings transactions to finish before cleaning up the session.
    daemon_threads = False

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(15)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, console, token, **kwargs):
        self.console = console
        self.token = token
        super().__init__(*args, **kwargs)

    def log_message(self, *_):
        pass

    @property
    def authority(self):
        return f"127.0.0.1:{self.server.server_port}"

    def reply(self, status, payload, kind="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("Host") != self.authority:
            return self.reply(403, {"error": "Open the local URL printed by DroidPilot."})
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8"),
                  "/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
                  "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        if self.path not in assets:
            return self.reply(404, {"error": "Unknown resource."})
        filename, kind = assets[self.path]
        body = files("droidpilot").joinpath("web", filename).read_bytes()
        if filename == "index.html":
            body = body.replace(b"__SESSION__", self.token.encode())
        self.reply(200, body, kind)

    def do_POST(self):
        if (self.headers.get("Host") != self.authority or
                self.headers.get("Origin") != "http://" + self.authority or
                self.headers.get("X-DroidPilot-Session") != self.token):
            return self.reply(403, {"error": "Session expired. Reload the local dashboard."})
        if self.path != "/api/device":
            return self.reply(404, {"error": "Unknown operation."})
        if self.headers.get_content_type() != "application/json":
            return self.reply(415, {"error": "Expected JSON."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2048:
                return self.reply(413, {"error": "Invalid request size."})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError
        except (ValueError, UnicodeError):
            return self.reply(400, {"error": "Invalid request."})
        try:
            self.reply(200, self.console.request(data))
        except PilotError as exc:
            self.reply(409, {"error": str(exc)})
        except OSError:
            self.reply(503, {"error": "Local device or backup storage is unavailable. Check permissions and refresh."})


def serve(port, open_browser):
    if not 0 <= port <= 65535:
        raise PilotError("Choose a port between 0 and 65535.")
    console = Console()
    handler = partial(Handler, console=console, token=secrets.token_urlsafe(32))
    try:
        with LocalServer(("127.0.0.1", port), handler) as server:
            url = f"http://127.0.0.1:{server.server_port}"
            print(f"DroidPilot Device Control Center: {url}\nPress Ctrl+C to stop.", flush=True)
            if open_browser:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    finally:
        console.close()
    return 0
