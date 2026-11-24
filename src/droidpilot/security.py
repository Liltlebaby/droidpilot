"""Read-only root, bootloader and boot-integrity inspection. Never invokes su."""
import re

PROP = re.compile(r"^\[([^\]]+)\]: \[(.*)\]$", re.M)
# One shell round trip. command -v only resolves paths; it never runs su or magisk.
PROBE = "echo selinux=$(getenforce); echo su=$(command -v su); echo magisk=$(command -v magisk)"
BOOT_STATES = {
    "green": ("ok", "Green · OS verified with the manufacturer key"),
    "yellow": ("warn", "Yellow · OS verified with a user-installed key"),
    "orange": ("warn", "Orange · bootloader unlocked, OS not verified"),
    "red": ("warn", "Red · verification failed"),
}


def parse_props(text):
    return dict(PROP.findall(text))


def parse_probe(text):
    values = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    return {key: values.get(key, "").strip() or None for key in ("selinux", "su", "magisk")}


def bootloader(props):
    flag, state = props.get("ro.boot.flash.locked"), props.get("ro.boot.vbmeta.device_state")
    if flag == "1" or state == "locked":
        return "ok", "Locked"
    if flag == "0" or state == "unlocked":
        return "warn", "Unlocked"
    return "info", "Not reported"


def assess(props, probe):
    rows = []

    def add(label, state, value):
        rows.append({"label": label, "state": state, "value": value})

    found = [f"{name} at {path}" for name, path in (("su", probe["su"]), ("magisk", probe["magisk"])) if path]
    add("Root access", "warn" if found else "ok", "; ".join(found) if found else "Not detected · no su or magisk binary")
    add("Bootloader", *bootloader(props))
    boot = props.get("ro.boot.verifiedbootstate")
    add("Verified boot", *BOOT_STATES.get(boot, ("info", boot or "Not reported")))
    verity = props.get("ro.boot.veritymode")
    if verity:
        add("dm-verity", "ok" if verity == "enforcing" else "warn", verity.capitalize())
    selinux = probe["selinux"]
    add("SELinux", "ok" if selinux == "Enforcing" else "warn" if selinux else "info", selinux or "Not reported")
    build_type, tags = props.get("ro.build.type", "unknown"), props.get("ro.build.tags", "unknown")
    stock = build_type == "user" and tags == "release-keys" and props.get("ro.debuggable") != "1"
    add("Build", "ok" if stock else "warn", f"{build_type} · {tags}" + (" · debuggable" if props.get("ro.debuggable") == "1" else ""))
    if "ro.crypto.state" in props:
        add("Storage encryption", "ok" if props["ro.crypto.state"] == "encrypted" else "warn",
            props["ro.crypto.state"].capitalize())
    add("Security patch", "info", props.get("ro.build.version.security_patch") or "Not reported")
    warranty = props.get("ro.boot.warranty_bit")
    if warranty is not None:
        add("Knox warranty bit", "ok" if warranty == "0" else "warn",
            "0 · not tripped" if warranty == "0" else f"{warranty} · tripped (permanent)")
    warnings = sum(row["state"] == "warn" for row in rows)
    summary = ("Stock and locked · no root detected" if not warnings
               else f"{warnings} modification{'s' if warnings > 1 else ''} detected")
    return {"summary": summary, "rooted": bool(found), "rows": rows}


def check(adb, device):
    props = parse_props(adb.command(device, "shell", "getprop"))
    return assess(props, parse_probe(adb.command(device, "shell", PROBE)))
