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

The model and release were read with `getprop`, the scales with `settings get global`, and the battery fields with `dumpsys battery`.

## Animation transaction

| Checkpoint | Window | Transition | Animator |
| --- | ---: | ---: | ---: |
| Initial read | 1.0× | 1.0× | 1.0× |
| Apply 1 read-back | 0.5× | 0.5× | 0.5× |
| Apply 2 read-back | 0.5× | 0.5× | 0.5× |
| Original values after Apply 2 | 1.0× | 1.0× | 1.0× |
| Restore and independent ADB read-back | 1.0× | 1.0× | 1.0× |

The demo shows the Dashboard during the transaction. The final segment shows the phone's Display Settings recorded separately with Android `screenrecord` after restoration. Audio and the phone's status bar are excluded. scrcpy recording exited on the Windows test host before it could start, so its live control remains unverified in this session. [Demo video](media/samsung-adb-demo.mp4) · [After second apply](media/samsung-animation-applied.png) · [After restore](media/samsung-animation-restored.png)

## Startup timing

All **10 of 10** launches of `com.android.settings/.Settings$DisplaySettingsActivity` returned a valid `TotalTime`. The median was **1,181.5 ms**, with a range of **1,129–1,323 ms**. The CLI ran `am force-stop` followed by `am start -W` on the same authorized Samsung over Wi-Fi ADB. These values describe this series on one handset. [Raw timings](measurements/samsung-display-settings.csv) · [Measurement metadata](measurements/samsung-display-settings.metadata.json)
