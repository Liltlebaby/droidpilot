"""Application service shared by the local dashboard and its integration tests."""
import hashlib
import hmac
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from . import animation
from .adb import ADB, Device, PilotError, RSA_HINT


class DemoADB(ADB):
    """A simulated settings provider. The transaction and read-back code is real."""
    def __init__(self):
        self.values = dict.fromkeys(animation.KEYS, "1.0")

    def devices(self):
        return [Device("sample-1", "device", "Pixel 8"), Device("sample-2", "offline", "Test handset")]

    def command(self, device, *args, timeout=15):
        if device.state != "device":
            raise PilotError("Sample handset is offline.")
        if args[:2] == ("shell", "getprop"):
            return {"ro.product.model": "Pixel 8", "ro.build.version.release": "14"}[args[2]]
        if args == ("shell", "dumpsys", "battery"):
            return "level: 78\nscale: 100\ntemperature: 312"
        if args[:2] == ("shell", "settings"):
            verb, _, key, *value = args[2:]
            if verb == "get":
                return self.values.get(key, "null")
            if verb == "put":
                self.values[key], = value
            elif verb == "delete":
                self.values.pop(key, None)
            return ""
        raise PilotError("Unsupported simulated operation.")


def battery_values(text):
    fields = dict(re.findall(r"^\s*(level|scale|temperature):\s*(-?\d+)\s*$", text, re.M))
    level, scale = int(fields.get("level", -1)), int(fields.get("scale", 0))
    percent = round(level * 100 / scale) if 0 <= level <= scale and scale else None
    temperature = int(fields["temperature"]) / 10 if "temperature" in fields else None
    return {"percent": percent, "temperature": temperature}


class Console:
    def __init__(self, live=None, directory=None):
        self.live = live or ADB()
        self.directory = directory
        self.demo = DemoADB()
        self.temp = tempfile.TemporaryDirectory(prefix="droidpilot-demo-")
        self.secret = secrets.token_bytes(32)
        self.lock = threading.Lock()
        self.mirrors = {}

    def close(self):
        for process in self.mirrors.values():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        self.temp.cleanup()

    def handle(self, mode, serial):
        return hmac.new(self.secret, f"{mode}/{serial}".encode(), hashlib.sha256).hexdigest()[:24]

    def request(self, data):
        mode, action = data.get("mode"), data.get("action")
        if mode not in ("demo", "live") or action not in ("list", "inspect", "apply", "restore", "mirror"):
            raise PilotError("Unknown workspace or operation.")
        with self.lock:
            adb = self.demo if mode == "demo" else self.live
            directory = Path(self.temp.name) if mode == "demo" else self.directory
            devices = adb.devices()
            if action == "list":
                return {"devices": [{"id": self.handle(mode, d.serial), "name": d.model or "Android device",
                                     "state": d.state} for d in devices]}
            device = next((d for d in devices if self.handle(mode, d.serial) == data.get("device")), None)
            if device is None:
                raise PilotError("Device disconnected or session expired. Refresh the device list.")
            if device.state != "device":
                raise PilotError(RSA_HINT if device.state == "unauthorized" else "Device is offline or unavailable.")
            if action in ("apply", "restore", "mirror") and data.get("confirmed") is not True:
                raise PilotError("Confirm this action on the selected device.")
            if action == "mirror":
                if mode != "live":
                    raise PilotError("Screen control requires a connected device in ADB mode.")
                return self.mirror(device)
            if action in ("apply", "restore"):
                animation.change(adb, device, action, directory)
            info = adb.info(device)
            current = animation.snapshot(adb, device)
            path = animation.backup_path(device, directory)
            original = animation.load_backup(path) if path.exists() else None
            try:
                battery = battery_values(adb.command(device, "shell", "dumpsys", "battery"))
            except PilotError:
                battery = {"percent": None, "temperature": None}
            return {**info, "current": current, "original": original, "battery": battery,
                    "mirrorAvailable": mode == "live" and bool(shutil.which("scrcpy"))}

    def mirror(self, device):
        previous = self.mirrors.get(device.serial)
        if previous and previous.poll() is None:
            return {"message": "Phone screen is already open."}
        executable = shutil.which("scrcpy")
        if not executable:
            raise PilotError("Install scrcpy and add its directory to PATH, then restart DroidPilot.")
        process = subprocess.Popen([executable, "--serial", device.serial, "--no-audio",
                                    "--window-title", "DroidPilot · Phone screen"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            process.wait(timeout=0.8)
        except subprocess.TimeoutExpired:
            self.mirrors[device.serial] = process
            return {"message": "Started scrcpy for the selected device."}
        raise PilotError("scrcpy exited during startup. Check the device connection and scrcpy version.")
