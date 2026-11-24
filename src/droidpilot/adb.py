"""ADB transport and device selection. Device commands always target one serial."""
import subprocess
from dataclasses import dataclass


class PilotError(Exception):
    """An actionable CLI error suitable for public terminal output."""


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    model: str = ""


def parse_devices(output):
    devices = []
    header_seen = False
    for line in output.splitlines():
        if line.strip() == "List of devices attached":
            header_seen = True
            continue
        if not header_seen or not line.strip() or line.startswith("*"):
            continue
        fields = line.split()
        if len(fields) < 2 or ":" in fields[1]:
            raise PilotError("Unexpected device list format. Inspect adb devices -l privately.")
        state = "no permissions" if fields[1:3] == ["no", "permissions"] else fields[1]
        model = next((field[6:].replace("_", " ") for field in fields[2:] if field.startswith("model:")), "")
        devices.append(Device(fields[0], state, model))
    if not header_seen:
        raise PilotError("Missing device list header. Check adb version and retry.")
    if len({d.serial for d in devices}) != len(devices):
        raise PilotError("Duplicate device identifiers. Reconnect one device at a time.")
    return devices


RSA_HINT = ("Enable Developer options and USB debugging, unlock the phone, "
            "then accept the RSA fingerprint prompt for your computer.")


class ADB:
    def run(self, args, timeout=15):
        try:
            proc = subprocess.run(["adb", *args], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
        except FileNotFoundError as exc:
            raise PilotError("adb is missing. Add Android SDK Platform Tools to PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise PilotError("adb timed out. Check the USB connection and retry.") from exc
        if proc.returncode:
            # ADB diagnostics may contain the complete device serial.
            raise PilotError(f"adb exited with code {proc.returncode}. Check the connection and device permissions.")
        if args[:1] == ["-s"] and proc.stderr.strip():
            raise PilotError("The selected device returned diagnostics. Check its permissions and retry.")
        return proc.stdout.strip()

    def devices(self):
        return parse_devices(self.run(["devices", "-l"]))

    def select(self, serial):
        for device in self.devices():
            if device.serial == serial:
                if device.state == "unauthorized":
                    raise PilotError(RSA_HINT)
                if device.state != "device":
                    raise PilotError("Selected device is not ready. Reconnect it and run doctor.")
                return device
        raise PilotError("Selected device was not found. Check adb devices -l privately.")

    def command(self, device, *args, timeout=15):
        if device.state != "device":
            raise PilotError("An authorized device is required.")
        return self.run(["-s", device.serial, *args], timeout=timeout)

    def info(self, device):
        return {key: self.command(device, "shell", "getprop", prop) or "unknown"
                for key, prop in (("model", "ro.product.model"),
                                  ("android_version", "ro.build.version.release"))}
