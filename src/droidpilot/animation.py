import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .adb import PilotError

KEYS = ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", re.ASCII)


def state_dir():
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "DroidPilot" / "backups"
    return Path(os.getenv("XDG_STATE_HOME") or Path.home() / ".local/state") / "droidpilot/backups"


@contextmanager
def device_lock(path):
    # OS releases this lock on process exit, including an interrupted run.
    with path.open("a+b") as handle:
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise PilotError("Device backup is busy. Wait for the other operation.") from exc
        yield


def valid(value):
    return value is None or (isinstance(value, str) and NUMBER.fullmatch(value))


def read(adb, device, key):
    result = adb.command(device, "shell", "settings", "get", "global", key)
    value = None if result == "null" else result
    if not valid(value):
        raise PilotError(f"Could not read a numeric or absent value for {key}.")
    return value


def snapshot(adb, device):
    return {key: read(adb, device, key) for key in KEYS}


def write_verified(adb, device, key, value):
    args = ["delete", "global", key] if value is None else ["put", "global", key, value]
    adb.command(device, "shell", "settings", *args)
    if read(adb, device, key) != value:
        raise PilotError(f"Read-back did not match for {key}.")


def save_backup(path, values):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8") as tmp:
        temporary = Path(tmp.name)
        try:
            json.dump(values, tmp)
            tmp.flush()
            os.fsync(tmp.fileno())
        except BaseException:
            tmp.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_backup(path):
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise PilotError("Unreadable backup. Keep it for manual inspection.") from exc
    if not isinstance(values, dict) or set(values) != set(KEYS) or not all(map(valid, values.values())):
        raise PilotError("Invalid backup. Keep it for manual inspection.")
    return values


def rollback(adb, device, before):
    unresolved = []
    for key, value in before.items():
        try:
            if read(adb, device, key) != value:
                write_verified(adb, device, key, value)
        except (PilotError, OSError):
            unresolved.append(key)
    return ", ".join(unresolved) or "none"


def backup_path(device, directory=None):
    directory = state_dir() if directory is None else directory
    stem = hashlib.sha256(device.serial.encode()).hexdigest()
    return directory / (stem + ".json")


def change(adb, device, action, directory=None):
    if action not in {"apply", "restore"}:
        raise PilotError("Unknown animation action.")
    path = backup_path(device, directory)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with device_lock(path.with_suffix(".lock")):
        before = snapshot(adb, device)
        if path.exists():
            original = load_backup(path)
        elif action == "apply":
            original = before
            save_backup(path, original)
        else:
            raise PilotError("No saved animation profile for this device.")
        target = dict.fromkeys(KEYS, "0.5") if action == "apply" else original
        try:
            for key, value in target.items():
                if before[key] != value:
                    write_verified(adb, device, key, value)
            if snapshot(adb, device) != target:
                raise PilotError("Final animation profile verification failed.")
        except (PilotError, OSError, KeyboardInterrupt) as exc:
            remaining = rollback(adb, device, before)
            raise PilotError(f"Change failed ({exc}). Backup retained. "
                             f"Unverified settings after rollback: {remaining}.") from exc
        if action == "restore":
            path.unlink()
        return target
