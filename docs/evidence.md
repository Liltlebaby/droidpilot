# Evidence record

This repository contains a new AI-assisted project. Evidence below distinguishes automated checks, simulated examples and real phone observations. Record a test date, model and Android release when adding a device result.

| Feature | Implementation | Automated evidence | Device-tested | Evidence to add |
| --- | --- | --- | --- | --- |
| Device Control Center | Implemented | Desktop and mobile browser checks; demo apply twice and restore; JSON API and confirmation checks | Live Samsung selection, telemetry, animation writes and restore | [Real Samsung dashboard screenshot](media/samsung-inspection.png) and [live ADB demo](media/samsung-adb-demo.mp4). scrcpy live control remains unverified |
| ADB Doctor | Implemented | Mock-tested; missing-ADB error exercised locally | Authorized wireless inventory and model/release reads on Samsung SM-A135F | Pre-authorization USB capture pending. [Handset observations](handset.md) |
| Animation | Implemented | Mock-tested with repeated apply, absent values, rollback and retry | Applied twice and restored all three verified values on Samsung SM-A135F | [Checkpoint values and screenshots](handset.md#animation-transaction) |
| Crash Triage | Implemented | Mock-tested and compared against an explicitly simulated example | Not tested | Sanitized crash report from an approved test app |
| Startup Timer | Implemented | Mock-tested for valid, missing and failed measurements | 10/10 Display Settings launches on Samsung SM-A135F | [CSV, metadata and median](handset.md#startup-timing) |
| Magisk Boot Report | Implemented | ZIP contents, LF endings and POSIX syntax checked locally | Not tested | Two reports after two separately approved boots |

## Capture a device demo

- Start with Doctor. On a new connection, run `doctor` while the authorization prompt is pending, then again after the device owner accepts. If the computer was already authorized, record that fact. Keep the serial lookup and authorization dialog outside the recording.
- Use the four animation commands in the main README. Capture a short clip of the terminal and a repeated transition in Settings. Compare all three restored values with the original output.
- For startup timing, identify the exact app build, approved component and test conditions. Save a real ten-run CSV and its metadata together. Report the success count even if some runs failed.
- Review crash messages, paths, notifications, account names and identifiers before copying evidence into the repository. Keep raw captures under the ignored `private/` folder. Link reviewed samples here once available.
- Complete the Magisk row only when an appropriate device and approval for each reboot are available.

## Publish the portfolio

Choose a license if you wish to grant reuse rights. No license has been selected. Review the files and staged changes locally, including every public example. Create an empty GitHub repository under your account, add its URL as the remote and push only when you choose to publish. The project includes CI configuration. Add a workflow result after a real hosted run.

For an interview, demonstrate the source line in the fixture or a verified handset result, then explain the implementation choice behind it. For animation, show why a second apply preserves the same original snapshot. For startup, explain why an unsuccessful measurement remains empty when computing a median.
