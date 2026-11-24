import csv
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from droidpilot import animation, crash, startup
from droidpilot.__main__ import main
from droidpilot.adb import ADB, Device, PilotError, parse_devices
from droidpilot.doctor import diagnose

ROOT = Path(__file__).resolve().parents[1]
PHONE = Device("private-serial", "device")
HEADER = "List of devices attached\n"


def result(stdout="", code=0):
    return subprocess.CompletedProcess([], code, stdout, "private-serial" if code else "")


class DoctorTests(unittest.TestCase):
    def test_no_devices(self):
        with patch("subprocess.run", return_value=result(HEADER)), self.assertRaisesRegex(PilotError, "No devices"):
            diagnose(ADB())

    def test_mixed_does_not_select(self):
        output = HEADER + "private-serial device product:p\nother unauthorized\nthird offline\nfourth recovery\n"
        with patch("subprocess.run", return_value=result(output)) as run, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(diagnose(ADB()), 0)
            self.assertEqual(run.call_count, 1)
            for value in ("authorized", "RSA", "offline", "unsupported"):
                self.assertIn(value, out.getvalue())
            self.assertNotIn("private-serial", out.getvalue())

    def test_explicit_selection(self):
        with patch("subprocess.run", side_effect=[result(HEADER + "a device\nb device"),
                                                  result("Demo model"), result("14")]) as run, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(diagnose(ADB(), "b"), 0)
            self.assertIn("Demo model | Android 14", out.getvalue())
            for call in run.call_args_list[1:]:
                self.assertEqual(call.args[0][:4], ["adb", "-s", "b", "shell"])

    def test_unauthorized_offline_and_unknown_serial(self):
        for serial, state in (("a", "unauthorized"), ("a", "offline"), ("b", "device")):
            with self.subTest(state=state), patch("subprocess.run", return_value=result(HEADER + f"a {state}")) as run:
                with self.assertRaises(PilotError):
                    ADB().select(serial)
                self.assertEqual(run.call_count, 1)

    def test_malformed(self):
        for data in ("bad header", HEADER + "onefield", HEADER + "a device\na offline"):
            with self.subTest(data=data), self.assertRaises(PilotError):
                parse_devices(data)

    def test_missing_and_timeout(self):
        for error, msg in [(FileNotFoundError(), "missing"), (subprocess.TimeoutExpired([], 15), "timed out")]:
            with patch("subprocess.run", side_effect=error), self.assertRaisesRegex(PilotError, msg):
                ADB().devices()

    def test_error_redacts_serial(self):
        with patch("subprocess.run", return_value=result(code=1)), self.assertRaises(PilotError) as ctx:
            ADB().command(PHONE, "shell", "getprop")
        self.assertNotIn(PHONE.serial, str(ctx.exception))

    def test_stderr_with_success_status(self):
        diagnostic = subprocess.CompletedProcess([], 0, "", "Error from settings provider")
        with patch("subprocess.run", return_value=diagnostic), self.assertRaisesRegex(PilotError, "diagnostics"):
            ADB().command(PHONE, "shell", "settings", "get", "global", animation.KEYS[0])


class SettingsTransport:
    """A stateful subprocess stand-in for two independent settings providers."""
    def __init__(self):
        self.initial = dict(zip(animation.KEYS, ("1.00", None, "2")))
        self.devices = {}
        self.fail_once = None
        self.ignore_once = None

    def run(self, cmd, **kwargs):
        if cmd == ["adb", "devices", "-l"]:
            return result(HEADER + PHONE.serial + " device")
        binary, flag, serial, shell, settings, verb, namespace, key, *value = cmd
        assert (binary, flag, shell, settings, namespace) == ("adb", "-s", "shell", "settings", "global")
        state = self.devices.setdefault(serial, self.initial.copy())
        if verb == "get":
            return result(state[key] if state[key] is not None else "null")
        if self.fail_once == key:
            self.fail_once = None
            return result(code=1)
        if self.ignore_once == key:
            self.ignore_once = None
            return result()
        if verb == "put":
            state[key], = value
        elif verb == "delete":
            state[key] = None
        else:
            raise AssertionError(cmd)
        return result()


class AnimationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.transport = SettingsTransport()
        mock = patch("subprocess.run", side_effect=self.transport.run)
        self.run_mock = mock.start()
        self.addCleanup(mock.stop)

    def change(self, action, device=PHONE):
        return animation.change(ADB(), device, action, self.directory)

    def backups(self):
        return list(self.directory.glob("*.json"))

    def test_repeated_apply_and_restore_absence_and_exact_value(self):
        self.change("apply")
        self.change("apply")
        self.assertEqual(json.loads(self.backups()[0].read_text()), self.transport.initial)
        self.assertEqual(self.change("restore"), self.transport.initial)
        self.assertEqual(len(self.backups()), 0)
        self.assertEqual(self.transport.devices[PHONE.serial], self.transport.initial)

    def test_isolation(self):
        other = Device("second-test-device", "device")
        self.transport.devices[other.serial] = dict.fromkeys(animation.KEYS, "0")
        self.change("apply")
        self.change("apply", other)
        self.change("restore")
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.change("restore", other), dict.fromkeys(animation.KEYS, "0"))

    def test_failed_write_rolls_back(self):
        self.transport.fail_once = animation.KEYS[1]
        with self.assertRaisesRegex(PilotError, "after rollback: none"):
            self.change("apply")
        self.assertEqual(self.transport.devices[PHONE.serial], self.transport.initial)
        self.assertEqual(len(self.backups()), 1)

    def test_unverified_write_fails(self):
        self.transport.ignore_once = animation.KEYS[0]
        with self.assertRaisesRegex(PilotError, "Read-back"):
            self.change("apply")

    def test_failed_restore_is_retryable(self):
        profile = self.change("apply")
        self.transport.fail_once = animation.KEYS[1]
        with self.assertRaises(PilotError):
            self.change("restore")
        self.assertEqual(self.transport.devices[PHONE.serial], profile)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.change("restore"), self.transport.initial)

    def test_damaged_backup_refuses_write(self):
        self.change("apply")
        self.backups()[0].write_text("{}")
        self.run_mock.reset_mock()
        with self.assertRaisesRegex(PilotError, "Invalid backup"):
            self.change("apply")
        self.assertFalse(any("put" in c.args[0] for c in self.run_mock.call_args_list))

    def test_lock_contention_then_retry(self):
        path = self.directory / "device.lock"
        with animation.device_lock(path):
            with self.assertRaisesRegex(PilotError, "busy"), animation.device_lock(path):
                self.fail("second writer entered")
        with animation.device_lock(path):
            self.assertTrue(path.exists())

    def test_confirmation_precedes_writes(self):
        with patch("sys.stdin.isatty", return_value=False), redirect_stderr(io.StringIO()):
            self.assertEqual(main(["animation", "apply", "--serial", PHONE.serial]), 1)
        self.assertEqual(self.run_mock.call_count, 1)


class CrashTests(unittest.TestCase):
    def test_fixture(self):
        event, = crash.parse((ROOT / "examples/simulated-crash.log").read_text())
        self.assertEqual(event.process, "org.example.notes")
        self.assertEqual(event.thread, "main")
        self.assertIn("RuntimeException", event.exception)
        self.assertIn("NoteScreen.kt:42", event.application_frame())

    def test_nested_causes_and_interleaved_events(self):
        log = "\n".join(f"E/AndroidRuntime({pid}): {msg}" for pid, msg in [
            (10, "FATAL EXCEPTION: main"), (20, "FATAL EXCEPTION: io"),
            (10, "Process: org.one, PID: 10"), (20, "Process: org.two, PID: 20"),
            (10, "java.lang.RuntimeException: startup"), (10, "Caused by: a.b.Error: outer"),
            (10, "Caused by: c.d.Error: inner"), (20, "at org.two.Work.run(Work.kt:17)")])
        first, second = crash.parse(log)
        self.assertEqual(first.causes, ["a.b.Error: outer", "c.d.Error: inner"])
        self.assertIsNone(first.application_frame())
        self.assertIn("Work.kt:17", second.application_frame())
        self.assertEqual(second.exception, "unknown")

    def test_absent_and_empty(self):
        self.assertIn("Fatal events found: 0", crash.render(""))
        self.assertIn("Application frame: unknown", crash.render("E AndroidRuntime: FATAL EXCEPTION: worker"))

    def test_expected_report_matches_cli(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            output = Path(tmp) / "report.md"
            args = ["crash", "--input", str(ROOT / "examples/simulated-crash.log"), "--output", str(output)]
            self.assertEqual(main(args), 0)
            self.assertEqual(output.read_text(), (ROOT / "examples/expected-report.md").read_text())
            self.assertEqual(main(args), 1)

    def test_capture_preserves_buffer(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            with patch("subprocess.run", side_effect=[result(HEADER + "a device"), result("")]) as run:
                self.assertEqual(main(["crash", "--serial", "a", "--output", str(Path(tmp) / "report.md")]), 0)
                self.assertEqual(run.call_args.args[0], ["adb", "-s", "a", "logcat", "-b", "crash", "-d"])


class StartupTests(unittest.TestCase):
    def test_nested_settings_activity_preserves_dollar_sign(self):
        component = "com.android.settings/.Settings$DisplaySettingsActivity"
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            replies = [result("Samsung"), result("14"), result(), result("Status: ok\nTotalTime: 48")]
            with patch("subprocess.run", side_effect=replies) as run:
                code = startup.measure(ADB(), PHONE, component, 1, Path(tmp) / "runs.csv")
            self.assertEqual(code, 0)
            self.assertEqual(run.call_args.args[0][-1], "'" + component + "'")

    def test_timing(self):
        self.assertEqual(startup.timing("Status: ok\nTotalTime: 320"), 320)
        for data in ("Status: timeout\nTotalTime: 1", "Status: ok", "TotalTime: 10",
                     "Error: activity", "Status: ok\nTotalTime: -1", "Warning: reused\nStatus: ok\nTotalTime: 0"):
            with self.subTest(data=data), self.assertRaises(PilotError):
                startup.timing(data)

    def measure(self, responses, output):
        replies = [result("Example model"), result("15")]
        for response in responses:
            replies.extend((result(), result(response)))
        with patch("subprocess.run", side_effect=replies) as run, redirect_stdout(io.StringIO()) as out:
            code = startup.measure(ADB(), PHONE, "org.example/.Main", len(responses), output)
            for i in range(len(responses)):
                self.assertEqual(run.call_args_list[2+i*2].args[0][3:], ["shell", "am", "force-stop", "org.example"])
                self.assertEqual(run.call_args_list[3+i*2].args[0][3:], ["shell", "am", "start", "-W", "-n", "org.example/.Main"])
        return code, out.getvalue()

    def test_odd_and_even(self):
        for values, expected in [([11, 30, 12], 12), ([10, 11], 10.5)]:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "runs.csv"
                code, out = self.measure([f"Status: ok\nTotalTime: {n}" for n in values], path)
                self.assertEqual(code, 0)
                self.assertIn(f"Median TotalTime: {expected} ms", out)
                metadata = path.with_suffix(".metadata.json").read_text()
                self.assertIn("Example model", metadata)
                self.assertNotIn(PHONE.serial, metadata)

    def test_partial_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.csv"
            code, out = self.measure(["Status: ok\nTotalTime: 35", "Error: failed", "Status: ok"], path)
            self.assertEqual(code, 1)
            self.assertIn("1/3", out)
            self.assertIn("35 ms", out)
            with path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["total_time_ms"] for row in rows], ["35", "", ""])
            self.assertTrue(all(row["error"] for row in rows[1:]))

    def test_component_and_runs_validation(self):
        for component, runs in (("a/.Main;id", 2), ("missing", 1), ("a/.Main", 0)):
            with self.assertRaises(PilotError):
                startup.validate(component, runs)
