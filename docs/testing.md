# Verification

## Run the checks

Install the project with `python -m pip install -e .` in a Python 3.10+ virtual environment, or run from the source tree with `$env:PYTHONPATH = "src"` in PowerShell. The automated suite uses Python's standard library.

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m droidpilot --help
python -m droidpilot crash --input examples/simulated-crash.log --output crash-report.md
```

Use a new output path each time. The fixture test compares the complete generated Markdown with the checked-in expected report. On a system with a POSIX shell, run `sh -n magisk-boot-report/service.sh` for shell syntax validation.

## Local run record

Windows, Python 3.12.10. The source-tree runs used `PYTHONPATH=src`. The commands below show the underlying checks executed from the project root.

| Command or check | Observed result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 32 tests, including loopback HTTP, device-service integration and nested activity names |
| `python -m compileall -q src tests` | Exit 0 |
| `python -m droidpilot --help` | CLI entry point lists dashboard, doctor, animation, crash and startup |
| `python -m droidpilot crash --input examples/simulated-crash.log --output ../../work/final-simulated-report.md` | Exit 0. One simulated event. The same CLI path was compared with the expected Markdown in the suite |
| `python -m droidpilot doctor` | Exit 1 as expected on this host. Displayed instructions to add Platform Tools to PATH |
| `setuptools.build_meta.build_editable('../../work')` | Built the editable wheel using a workspace temporary directory. The host default temporary path contained braces that setuptools treated as substitution syntax |
| Magisk ZIP check using Python zipfile | Verified archive integrity, exact root entries and LF line endings for both files |
| `shfmt -ln posix magisk-boot-report/service.sh` | POSIX parse passed with shfmt 3.14.1 on Windows. Linux CI also runs `sh -n` |
| GitHub Actions | Configured for Windows and Linux. Hosted run pending publication |

## What the tests exercise

- **Control Center.** The API tests exercise the packaged assets, host and origin restrictions, session token, bounded requests, disconnected devices and isolated live/demo handles. Browser checks exercise cancel, apply twice, read-back, restore, an offline selection and a 390-pixel mobile viewport. The README screenshot was captured in Chrome at 1440 × 900.

To rebuild the production bundle and run the browser suite, use a recent Node.js LTS and Python on PATH. From the repository root:

```powershell
cd frontend
npm ci
npm run build
npx playwright install chromium
npm test
```

The browser tests start a dedicated Python process on an ephemeral loopback port and select the simulated device. Set `DROIDPILOT_TEST_BROWSER` to an existing Chrome executable to use an installed browser. The CI job rebuilds the committed bundle and checks it for drift.

- **ADB.** Mock subprocess responses cover missing tools, timeout, malformed inventory, offline and unauthorized devices, redaction and explicit selection among multiple devices.
- **Animation.** A stateful settings provider supports exact strings, absent keys, write failures and ignored writes. Tests check restoration after two applies, per-device isolation, lock contention, rollback, retry and damaged backups.
- **Crash.** Real parser and renderer code run against synthetic threadtime and brief-format events, including interleaved process IDs, nested causes, absent app frames and empty input.
- **Startup.** Mock activity-manager output drives the real CSV writer and summary calculation. Tests cover command ordering, odd and even medians, partial failures, missing timings and component validation.

Wireless ADB inspection was separately exercised on a Samsung SM-A135F with Android 14. The live dashboard read the three current scales and battery telemetry and supplied the README image. [Handset evidence](handset.md)
