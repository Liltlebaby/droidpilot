import csv
import json
import re
import shlex
from datetime import datetime, timezone
from statistics import median

from .adb import PilotError

PACKAGE = r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*"
ACTIVITY = r"\.?[A-Za-z_][A-Za-z0-9_]*(?:[.$][A-Za-z_][A-Za-z0-9_]*)*"
COLUMNS = ("run", "timestamp_utc", "status", "total_time_ms", "error")


def validate(component, runs):
    if not re.fullmatch(PACKAGE + "/" + ACTIVITY, component):
        raise PilotError("Use PACKAGE/ACTIVITY, e.g. com.example.demo/.MainActivity.")
    if runs < 1:
        raise PilotError("--runs must be positive.")


def timing(output):
    fields = {}
    for line in output.splitlines():
        key, _, value = line.strip().partition(":")
        fields[key] = value.strip()
    if fields.get("Status") != "ok" or "Error" in fields or "Error type 3" in fields:
        raise PilotError("Launch failed or Status was missing. Check the activity and permissions.")
    if "Warning" in fields:
        raise PilotError("Launch warning. Activity may have been reused.")
    total = fields.get("TotalTime", "")
    if not re.fullmatch(r"[0-9]+", total):
        raise PilotError("TotalTime was missing or invalid.")
    return int(total)


def measure(adb, device, component, runs, output):
    validate(component, runs)
    metadata = {"component": component, **adb.info(device),
                "method": "force-stop followed by am start -W", "requested_runs": runs}
    package = component.split("/")[0]
    times = []
    meta_path = output.with_suffix(".metadata.json")
    if meta_path == output or output.exists() or meta_path.exists():
        raise PilotError("Choose a fresh CSV filename and metadata filename.")
    # Exclusive creation prevents accidental overwrite. Flush completed rows for interrupted runs.
    with output.open("x", encoding="utf-8", newline="") as handle:
        with meta_path.open("x", encoding="utf-8") as meta:
            json.dump(metadata, meta, indent=2)
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for run in range(1, runs + 1):
            stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            row = dict(run=run, timestamp_utc=stamp, status="failed", total_time_ms="", error="")
            try:
                stopped = adb.command(device, "shell", "am", "force-stop", package)
                if stopped:
                    raise PilotError("Force-stop returned diagnostics. Check the selected app.")
                # ADB forwards these arguments to the device shell. Preserve nested class names.
                result = adb.command(device, "shell", "am", "start", "-W", "-n", shlex.quote(component), timeout=60)
                elapsed = timing(result)
                times.append(elapsed)
                row.update(status="ok", total_time_ms=elapsed)
            except PilotError as exc:
                row["error"] = str(exc)
            writer.writerow(row)
            handle.flush()
    print(f"Successful runs: {len(times)}/{runs}")
    print(f"Median TotalTime: {median(times):g} ms" if times else "Median TotalTime: unavailable")
    return 0 if len(times) == runs else 1
