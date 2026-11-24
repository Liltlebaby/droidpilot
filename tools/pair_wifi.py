"""Pair an owned Android 11+ phone using the pairing dialog on its screen."""
import ipaddress
import subprocess
import sys


def endpoint(label):
    while True:
        raw = input(label).strip()
        if not raw:
            return None
        if len(raw) == 6 and raw.isdecimal():
            print("That is a pairing code. First enter the IP address AND port shown below it, e.g. 192.168.1.42:37123.")
            continue
        host, separator, port = raw.rpartition(":")
        try:
            address = ipaddress.ip_address(host.strip("[]"))
            number = int(port)
            if separator and 1 <= number <= 65535:
                return f"[{address}]:{number}" if address.version == 6 else f"{address}:{number}"
        except ValueError:
            pass
        print("Enter the IP address and port exactly as shown on the phone.")


def main():
    print("On the phone open Wireless debugging > Pair device with pairing code.")
    pairing = endpoint("Step 1 - enter IP:port from the pairing dialog (Enter to cancel): ")
    if not pairing:
        return 0
    print("Enter the six-digit code directly at the ADB prompt.")
    paired = subprocess.run(["adb", "pair", pairing], timeout=120)
    if paired.returncode:
        print("Pairing failed. Open a fresh pairing dialog on the phone and retry.")
        return 1
    print("Return to the main Wireless debugging screen. Its connection port may differ.")
    address = endpoint("Connection IP:port (Enter if already connected automatically): ")
    if address:
        subprocess.run(["adb", "connect", address], check=True, timeout=20)
    from droidpilot.adb import ADB
    from droidpilot.doctor import diagnose
    return diagnose(ADB())


if __name__ == "__main__":
    from droidpilot.adb import PilotError
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        sys.exit(1)
    except (OSError, subprocess.SubprocessError, PilotError) as error:
        print(f"Unable to finish pairing: {error}", file=sys.stderr)
        sys.exit(1)
