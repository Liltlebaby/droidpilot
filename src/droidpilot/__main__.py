import argparse
import sys
from pathlib import Path

from . import animation, crash, startup
from .adb import ADB, PilotError
from .doctor import diagnose


def parser():
    cli = argparse.ArgumentParser(prog="droidpilot", description="Android engineering tools for authorized devices.")
    commands = cli.add_subparsers(dest="command", required=True)
    ui = commands.add_parser("dashboard", help="open the local Device Control Center")
    ui.add_argument("--port", type=int, default=8765, help="loopback HTTP port (default 8765)")
    ui.add_argument("--no-browser", action="store_true", help="print the URL without opening a browser")
    doctor = commands.add_parser("doctor", help="inspect ADB connections with redacted serials")
    doctor.add_argument("--serial", help="select one device for detailed inspection")
    anim = commands.add_parser("animation", help="inspect or change global animation scales")
    anim.add_argument("action", choices=("show", "apply", "restore"))
    anim.add_argument("--serial", required=True)
    anim.add_argument("--yes", action="store_true", help="approve the requested settings change")
    logs = commands.add_parser("crash", help="triage AndroidRuntime crash logs")
    source = logs.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="UTF-8 log file")
    source.add_argument("--serial", help="read the crash buffer on this device")
    logs.add_argument("--output", type=Path, required=True, help="new Markdown file")
    launch = commands.add_parser("startup", help="time force-stop-based launches of a test app")
    launch.add_argument("--serial", required=True)
    launch.add_argument("--component", required=True, help="approved test app PACKAGE/ACTIVITY")
    launch.add_argument("--runs", type=int, default=10)
    launch.add_argument("--output", type=Path, required=True, help="new CSV file")
    launch.add_argument("--yes", action="store_true", help="approve force-stopping and launching this app")
    return cli


def approve(prompt, yes):
    if yes:
        return
    if not sys.stdin.isatty() or input(prompt + " [y/N] ").strip().lower() not in ("y", "yes"):
        raise PilotError("Operation was not approved. Use --yes to approve explicitly.")


def execute(args):
    if args.command == "dashboard":
        from .dashboard import serve
        return serve(args.port, not args.no_browser)
    adb = ADB()
    if args.command == "doctor":
        return diagnose(adb, args.serial)
    if args.command == "crash":
        print(crash.PRIVACY, file=sys.stderr)
        if args.input is not None:
            data = args.input.read_text(encoding="utf-8-sig", errors="replace")
        else:
            device = adb.select(args.serial)
            data = adb.command(device, "logcat", "-b", "crash", "-d", timeout=30)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(crash.render(data))
        print(f"Wrote {args.output.name}")
        return 0
    device = adb.select(args.serial)
    if args.command == "animation":
        if args.action == "show":
            values = animation.snapshot(adb, device)
        else:
            approve(f"{args.action.capitalize()} animation settings on the selected device?", args.yes)
            values = animation.change(adb, device, args.action)
        for key, value in values.items():
            print(f"{key}: {'(absent)' if value is None else value}")
        return 0
    startup.validate(args.component, args.runs)
    approve(f"Force-stop and launch {args.component} {args.runs} time(s)?", args.yes)
    return startup.measure(adb, device, args.component, args.runs, args.output)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return execute(args)
    except FileExistsError:
        print("Error: output already exists. Choose a new file.", file=sys.stderr)
    except (OSError, PilotError, EOFError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
