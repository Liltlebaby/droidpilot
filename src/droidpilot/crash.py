"""Parse Java/Kotlin AndroidRuntime crashes from threadtime or brief logcat."""
import re
from dataclasses import dataclass, field

TAG = re.compile(r"\bAndroidRuntime(?:\(\s*(\d+)\))?\s*:\s?(.*)$")
THREAD_PID = re.compile(r"\b(\d+)\s+\d+\s+[VDIWEFAS]\s+$")
EXCEPTION = re.compile(r"([\w$]+(?:\.[\w$]+)+)(?::\s*(.*))?$")
FRAME = re.compile(r"at\s+([\w.$<>-]+)\(([^()]+)\)")
PRIVACY = "Crash logs and reports can contain personal data. Review and sanitize before publication."


@dataclass
class Crash:
    thread: str
    process: str = "unknown"
    exception: str = "unknown"
    causes: list[str] = field(default_factory=list)
    frames: list[tuple[str, str]] = field(default_factory=list)

    def application_frame(self):
        if self.process == "unknown":
            return None
        prefix = self.process.split(":")[0] + "."
        for method, location in self.frames:
            if method.startswith(prefix) and re.search(r":\d+$", location):
                return f"{method}({location})"
        return None


def parse(text):
    events = []
    current = {}
    for line in text.splitlines():
        tag = TAG.search(line)
        if not tag:
            continue
        match = THREAD_PID.search(line[:tag.start()])
        pid = tag[1] or (match[1] if match else "unknown")
        message = tag[2].strip()
        if message.startswith("FATAL EXCEPTION:"):
            event = Crash(message.partition(":")[2].strip() or "unknown")
            current[pid] = event
            events.append(event)
            continue
        event = current.get(pid)
        if event is None:
            continue
        process = re.match(r"Process:\s*([^,\s]+)", message)
        if process:
            event.process = process[1]
        elif message.startswith("Caused by:"):
            event.causes.append(message.partition(":")[2].strip() or "unknown")
        elif frame := FRAME.fullmatch(message):
            event.frames.append(frame.groups())
        elif event.exception == "unknown" and EXCEPTION.fullmatch(message):
            event.exception = message
    return events


def render(text):
    events = parse(text)
    lines = ["# Android crash report", ""]
    if text.startswith("# Simulated fixture."):
        lines.extend(["Source: simulated fixture for parser testing.", ""])
    lines.extend([PRIVACY, "", f"Fatal events found: {len(events)}"])
    if not events:
        lines.extend(["", "No AndroidRuntime fatal exception was found in this input."])
    for number, event in enumerate(events, 1):
        frame = event.application_frame()
        lines.extend(["", f"## Event {number}", "", f"    Thread: {event.thread}",
                      f"    Process: {event.process}", f"    Exception: {event.exception}",
                      "    Causes: " + (" -> ".join(event.causes) or "unknown"),
                      f"    Application frame: {frame or 'unknown'}", "",
                      "Next investigation point: inspect the application source line above."
                      if frame else "Next investigation point: obtain an unobfuscated application frame with a source line."])
    return "\n".join(lines) + "\n"
