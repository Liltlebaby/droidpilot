import tempfile
import unittest
from pathlib import Path

from droidpilot import security
from droidpilot.console import Console, DemoADB

STOCK = """[ro.boot.flash.locked]: [1]
[ro.boot.vbmeta.device_state]: [locked]
[ro.boot.verifiedbootstate]: [green]
[ro.boot.veritymode]: [enforcing]
[ro.boot.warranty_bit]: [0]
[ro.build.tags]: [release-keys]
[ro.build.type]: [user]
[ro.build.version.security_patch]: [2026-02-05]
[ro.crypto.state]: [encrypted]
[ro.debuggable]: [0]"""


def states(report):
    return {row["label"]: row["state"] for row in report["rows"]}


class SecurityTests(unittest.TestCase):
    def test_stock_locked_handset(self):
        report = security.assess(security.parse_props(STOCK),
                                 security.parse_probe("selinux=Enforcing\nsu=\nmagisk="))
        self.assertFalse(report["rooted"])
        self.assertEqual(report["summary"], "Stock and locked · no root detected")
        self.assertNotIn("warn", states(report).values())
        self.assertEqual(states(report)["Security patch"], "info")

    def test_unlocked_magisk_handset(self):
        props = security.parse_props(STOCK.replace("[1]", "[0]").replace("[locked]", "[unlocked]")
                                     .replace("[green]", "[orange]").replace("warranty_bit]: [0]", "warranty_bit]: [1]"))
        probe = security.parse_probe("selinux=Permissive\nsu=/debug_ramdisk/su\nmagisk=/debug_ramdisk/magisk")
        report = security.assess(props, probe)
        self.assertTrue(report["rooted"])
        rows = {row["label"]: row for row in report["rows"]}
        self.assertIn("/debug_ramdisk/su", rows["Root access"]["value"])
        for label in ("Root access", "Bootloader", "Verified boot", "SELinux", "Knox warranty bit"):
            self.assertEqual(rows[label]["state"], "warn", label)
        self.assertIn("permanent", rows["Knox warranty bit"]["value"])
        self.assertEqual(report["summary"], "5 modifications detected")

    def test_missing_properties_are_reported_not_guessed(self):
        report = security.assess({}, security.parse_probe(""))
        rows = {row["label"]: row for row in report["rows"]}
        self.assertEqual(rows["Bootloader"]["value"], "Not reported")
        self.assertEqual(rows["SELinux"]["state"], "info")
        self.assertNotIn("Knox warranty bit", rows)

    def test_inspect_returns_report_and_redacted_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            console = Console(DemoADB(), Path(directory))
            self.addCleanup(console.close)
            device = console.request({"mode": "demo", "action": "list"})["devices"][0]["id"]
            result = console.request({"mode": "demo", "action": "inspect", "device": device})
        self.assertEqual(result["security"]["summary"], "Stock and locked · no root detected")
        self.assertIn("adb -s <device> shell getprop", result["commands"])
        self.assertTrue(all("sample-1" not in command for command in result["commands"]))
        self.assertTrue(any("command -v su" in command for command in result["commands"]))


if __name__ == "__main__":
    unittest.main()
