from .adb import PilotError, RSA_HINT


def diagnose(adb, serial=None):
    devices = [adb.select(serial)] if serial else adb.devices()
    if not devices:
        raise PilotError("No devices. Connect a data cable, enable USB debugging, then run doctor.")
    ready = False
    for number, device in enumerate(devices, 1):
        label = f"Device {number}"
        if device.state == "device":
            ready = True
            if len(devices) == 1:
                info = adb.info(device)
                print(f"{label}: authorized | {info['model']} | Android {info['android_version']}")
            else:
                print(f"{label}: authorized. Use doctor --serial SERIAL for details.")
        elif device.state == "unauthorized":
            print(f"{label}: unauthorized. {RSA_HINT}")
        elif device.state == "offline":
            print(f"{label}: offline. Reconnect the cable and unlock the screen.")
        else:
            print(f"{label}: unsupported device state. Inspect adb devices -l privately.")
    return 0 if ready else 1
