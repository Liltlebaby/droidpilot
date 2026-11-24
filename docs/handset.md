# Samsung handset verification

A Windows workstation paired with an owned Samsung SM-A135F over Android Wireless debugging. The phone reported Android 14. The following values came from live ADB shell commands on 24 November 2026 (Asia/Bangkok). Device identifiers, pairing details and network addresses are omitted.

| Observation | Device response |
| --- | --- |
| ADB transport state | device (authorized) |
| Android release | 14 |
| Device model | SM-A135F |
| Window animation scale | 1.0 |
| Transition animation scale | 1.0 |
| Animator duration scale | 1.0 |
| Battery at inspection | 97% |
| Battery temperature at inspection | 31.2 °C |

The model and release were read with `getprop`, the scales with `settings get global`, and the battery fields with `dumpsys battery`. This record covers connection and inspection. Write verification, timing measurements and on-device recording have separate evidence requirements.
