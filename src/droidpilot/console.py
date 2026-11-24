"""Application service shared by the local dashboard and its integration tests."""
import hashlib
import hmac
import re
import secrets
import shlex
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from . import animation, security
from .adb import ADB, Device, PilotError, RSA_HINT

DEMO_PROPS = {"ro.product.model": "Pixel 8", "ro.build.version.release": "14",
              "ro.boot.verifiedbootstate": "green", "ro.boot.flash.locked": "1",
              "ro.boot.vbmeta.device_state": "locked", "ro.build.type": "user",
              "ro.build.tags": "release-keys", "ro.debuggable": "0", "ro.crypto.state": "encrypted",
              "ro.build.version.security_patch": "2026-10-05"}


class DemoADB(ADB):
    """A simulated settings provider. The transaction and read-back code is real."""
    def __init__(self):
        self.values = dict.fromkeys(animation.KEYS, "1.0")

    def devices(self):
        return [Device("sample-1", "device", "Pixel 8"), Device("sample-2", "offline", "Test handset")]

    def command(self, device, *args, timeout=15):
        if device.state != "device":
            raise PilotError("Sample handset is offline.")
        if args == ("shell", "getprop"):
            return "\n".join(f"[{key}]: [{value}]" for key, value in DEMO_PROPS.items())
        if args == ("shell", security.PROBE):
            return "selinux=Enforcing\nsu=\nmagisk="
        if args[:2] == ("shell", "getprop"):
            return DEMO_PROPS[args[2]]
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


class Recorder:
    """Delegates to a transport and records each command with the serial redacted."""
    def __init__(self, adb):
        self.adb, self.log = adb, []

    def devices(self):
        self.log.append("adb devices -l")
        return self.adb.devices()

    def command(self, device, *args, timeout=15):
        self.log.append("adb -s <device> " + " ".join(map(shlex.quote, args)))
        return self.adb.command(device, *args, timeout=timeout)

    def info(self, device):
        return ADB.info(self, device)


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
            adb = Recorder(self.demo if mode == "demo" else self.live)
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
                return {**self.mirror(device), "commands": [*adb.log, "scrcpy --serial <device> --no-audio"]}
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
            try:
                integrity = security.check(adb, device)
            except PilotError:
                integrity = None
            return {**info, "current": current, "original": original, "battery": battery,
                    "security": integrity, "commands": adb.log,
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
