# Magisk Boot Report

This optional module targets an owned, already rooted phone with Magisk installed. Its late-start service writes one UTC-stamped text file per execution under `/data/adb/modules/droidpilot_boot_report/reports/`. Each file contains the Android and kernel releases, uptime in seconds and the per-boot ID when available. Missing fields are labeled. Keep full boot IDs private.

The script uses a private creation mask, writes a temporary file in the reports directory, renames it on completion and retains ten completed reports. When the device clock changes, retention follows the UTC filename order. Uptime is sampled when the service runs. [Magisk module developer guide](https://topjohnwu.github.io/Magisk/guides.html)

## Package in PowerShell

Run these commands from the repository root. The ZIP entries must be at the archive root. Preserve LF endings for both files. This package targets installation through the Magisk app.

```powershell
Compress-Archive -Path magisk-boot-report/module.prop,magisk-boot-report/service.sh -DestinationPath droidpilot-boot-report.zip
python -m zipfile -l droidpilot-boot-report.zip
```

## Authorized hardware validation

1. Confirm the operator approves installation on this specific Magisk test phone. Copy the ZIP to the phone. In the Magisk app, open Modules, choose Install from storage and select the ZIP.
2. When the operator approves a reboot, reboot manually. Inspect the reports directory with an authorized root-capable file viewer. Record the timestamp and confirm the expected fields exist.
3. After separate approval for a second reboot, repeat the check. Compare the two per-boot IDs privately if available. Share sanitized reports with the timestamps and a note on whether the IDs differed.
4. To remove the module, select Remove in the Magisk app and reboot when approved. Save any required sanitized evidence first because the module directory contains its reports.

**Verification status:** untested on a device. Local packaging checks inspect the two entries and line endings. CI includes a POSIX shell syntax check. See the host validation record for its execution status. [Testing notes](../docs/testing.md)
