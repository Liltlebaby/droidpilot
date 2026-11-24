import json
import tempfile
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import Mock

from droidpilot import animation
from droidpilot.adb import Device, PilotError
from droidpilot.console import Console, DemoADB, battery_values
from droidpilot.dashboard import Handler, LocalServer


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.live = DemoADB()
        self.console = Console(self.live, self.directory)
        self.addCleanup(self.console.close)

    def test_profiles_stay_separate(self):
        demo = self.console.request({"mode": "demo", "action": "list"})["devices"][0]
        live = self.console.request({"mode": "live", "action": "list"})["devices"][0]
        self.assertNotEqual(demo["id"], live["id"])
        self.assertNotIn("sample-1", json.dumps(live))
        for mode, device in (("live", demo), ("demo", live)):
            with self.assertRaisesRegex(PilotError, "disconnected"):
                self.console.request(dict(mode=mode, device=device["id"], action="apply", confirmed=True))

        base = dict(mode="demo", device=demo["id"], confirmed=True)
        self.assertIsNone(self.console.request(dict(base, action="inspect"))["original"])
        for _ in range(2):
            applied = self.console.request(dict(base, action="apply"))
            self.assertEqual(applied["current"], dict.fromkeys(animation.KEYS, "0.5"))
            self.assertEqual(applied["original"], dict.fromkeys(animation.KEYS, "1.0"))
        restored = self.console.request(dict(base, action="restore"))
        self.assertIsNone(restored["original"])
        self.assertEqual(restored["current"], applied["original"])
        self.assertFalse(list(self.directory.iterdir()))
        self.assertEqual(self.live.values, restored["current"])

    def test_rechecks_device_before_confirmed_action(self):
        active = self.console.request({"mode": "live", "action": "list"})["devices"][0]["id"]
        self.live.devices = Mock(return_value=[Device("sample-1", "unauthorized")])
        with self.assertRaisesRegex(PilotError, "RSA"):
            self.console.request(dict(mode="live", action="apply", confirmed=True, device=active))
        self.assertFalse(list(self.directory.iterdir()))

    def test_confirmation_and_demo_mirror(self):
        device = self.console.request(dict(mode="demo", action="list"))["devices"][0]["id"]
        for action in ("apply", "restore", "mirror"):
            with self.assertRaisesRegex(PilotError, "Confirm"):
                self.console.request(dict(mode="demo", action=action, device=device))
        with self.assertRaisesRegex(PilotError, "connected device"):
            self.console.request(dict(mode="demo", action="mirror", confirmed=True, device=device))

    def test_battery_scale_and_missing_fields(self):
        self.assertEqual(battery_values("level: 60\nscale: 80\ntemperature: 294"), {"percent": 75, "temperature": 29.4})
        self.assertEqual(battery_values("level: 80\nscale: 0"), {"percent": None, "temperature": None})


class EndpointTests(unittest.TestCase):
    def setUp(self):
        console = Console()
        self.addCleanup(console.close)
        server = LocalServer(("127.0.0.1", 0), partial(Handler, console=console, token="test-token"))
        self.port = server.server_port
        self.addCleanup(server.server_close)
        self.thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join)
        self.addCleanup(server.shutdown)
        self.headers = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}",
                        "X-DroidPilot-Session": "test-token"}

    def exchange(self, method, path, body=None, headers=None):
        client = HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            client.request(method, path, body, headers or {})
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def test_serves_built_assets_and_rejects_unknown_paths(self):
        status, html = self.exchange("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"test-token", html)
        for name in ("dashboard.js", "dashboard.css", "favicon.svg"):
            status, asset = self.exchange("GET", "/" + name)
            self.assertEqual(status, 200)
            self.assertGreater(len(asset), 50)
        self.assertEqual(self.exchange("GET", "/README.md")[0], 404)
        self.assertEqual(self.exchange("GET", "/", headers={"Host": "other.example"})[0], 403)

    def test_api_contract(self):
        payload = json.dumps({"mode": "demo", "action": "list"})
        for key, bad in (("Origin", "https://other.example"), ("X-DroidPilot-Session", "expired")):
            headers = dict(self.headers, **{key: bad})
            self.assertEqual(self.exchange("POST", "/api/device", payload, headers)[0], 403)
        self.assertEqual(self.exchange("POST", "/api/device", "x" * 2100, self.headers)[0], 413)
        self.assertEqual(self.exchange("POST", "/api/device", "null", self.headers)[0], 400)
        status, result = self.exchange("POST", "/api/device", payload, self.headers)
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(result)["devices"]), 2)
