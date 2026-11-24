import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Device, Details, Mode, Operation, request } from "./api";
import { Confirmation, Profile } from "./Profile";
import { Commands, Security } from "./Security";
import "./style.css";

const statuses: Record<string, string> = {
  device: "Ready",
  unauthorized: "Awaiting authorization",
  offline: "Offline",
};
const advice = (state: string) =>
  state === "unauthorized"
    ? "Unlock the phone and accept its USB debugging prompt, then refresh."
    : "Reconnect the handset and refresh the device list.";
type Event = { time: string; message: string };
function Workspace({
  mode,
  setWriting,
}: {
  mode: Mode;
  setWriting: (value: boolean) => void;
}) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [active, setActive] = useState<Device | null>(null);
  const [info, setInfo] = useState<Details | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [pending, setPending] = useState<Operation | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [commands, setCommands] = useState<string[]>([]);
  const sequence = useRef(0);
  const log = (message: string) =>
    setEvents((prev) =>
      [
        {
          time: new Date().toLocaleTimeString("en-GB"),
          message,
        },
        ...prev,
      ].slice(0, 12),
    );
  function failure(reason: unknown) {
    const msg = reason instanceof Error ? reason.message : "Operation failed.";
    setError(msg);
    log(msg);
  }
  async function inspect(device: Device, seq: number) {
    setActive(device);
    setInfo(null);
    if (device.state !== "device") return;
    const details = await request<Details>(mode, "inspect", device.id);
    if (seq === sequence.current) {
      setInfo(details);
      setCommands(details.commands);
      log("Read device profile · " + details.model);
    }
  }
  async function load(keep?: string) {
    const seq = ++sequence.current;
    setBusy(true);
    setError("");
    setInfo(null);
    setActive(null);
    setDevices([]);
    try {
      const result = await request<{ devices: Device[] }>(mode, "list");
      if (seq !== sequence.current) return;
      setDevices(result.devices);
      const pick =
        result.devices.find((d) => d.id === keep) ??
        (mode === "demo" ? result.devices[0] : undefined);
      if (pick) await inspect(pick, seq);
    } catch (e) {
      if (seq === sequence.current) failure(e);
    } finally {
      if (seq === sequence.current) setBusy(false);
    }
  }
  useEffect(() => {
    void load();
    return () => {
      ++sequence.current;
    };
  }, [mode]);
  async function select(d: Device) {
    const seq = ++sequence.current;
    setBusy(true);
    setError("");
    try {
      await inspect(d, seq);
    } catch (e) {
      if (seq === sequence.current) failure(e);
    } finally {
      if (seq === sequence.current) setBusy(false);
    }
  }
  async function perform() {
    if (!pending || !active) return;
    const action = pending;
    setPending(null);
    setBusy(true);
    setWriting(true);
    setError("");
    try {
      if (action === "mirror") {
        const result = await request<{ message: string; commands: string[] }>(
          mode,
          action,
          active.id,
          true,
        );
        setCommands(result.commands);
        log(result.message);
      } else {
        const result = await request<Details>(mode, action, active.id, true);
        setInfo(result);
        setCommands(result.commands);
        log(
          (action === "apply" ? "Applied 0.5×" : "Restored original profile") +
            " · 3 values verified",
        );
      }
    } catch (e) {
      failure(e);
      if (action !== "mirror") {
        try {
          setInfo(await request<Details>(mode, "inspect", active.id));
        } catch {
          setInfo(null);
        }
      }
    } finally {
      setBusy(false);
      setWriting(false);
    }
  }
  return (
    <div className="layout">
      <aside>
        <div className="sidehead">
          <h2>Devices</h2>
          <button
            className="small"
            disabled={busy}
            onClick={() => void load(active?.id)}
          >
            ↻ Refresh
          </button>
        </div>
        <nav aria-label="Devices">
          {devices.map((d) => (
            <button
              className={"device " + (active?.id === d.id ? "selected" : "")}
              key={d.id}
              disabled={busy}
              onClick={() => void select(d)}
              aria-pressed={active?.id === d.id}
            >
              <span className="phone-icon" aria-hidden="true"></span>
              <span>
                <b>{d.name}</b>
                <small>
                  <i className={d.state === "device" ? "ready" : ""} />
                  {statuses[d.state] ?? "Unavailable"}
                  {mode === "live" && " · " + d.id.slice(0, 4)}
                </small>
              </span>
            </button>
          ))}
        </nav>
        {!devices.length && (
          <p className="aside-note">
            {busy ? "Scanning…" : "No devices listed."}
          </p>
        )}
      </aside>
      <main aria-busy={busy}>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {info && active ? (
          <>
            <div className="detailhead">
              <div className="device-title">
                <h1>{info.model}</h1>
                <span>Android {info.android_version}</span>
                <span>{mode === "demo" ? "Sample device" : "ADB device"}</span>
                {info.security && (
                  <span className={info.security.rooted ? "rooted" : ""}>
                    {info.security.rooted ? "Root detected" : "Not rooted"}
                  </span>
                )}
              </div>
              <button
                disabled={!info.mirrorAvailable || busy}
                title={
                  mode === "demo"
                    ? "Requires a real device in ADB mode"
                    : "Open with scrcpy"
                }
                onClick={() => setPending("mirror")}
              >
                ↗ Open phone screen
              </button>
            </div>
            <dl className="metrics">
              {[
                [
                  "Battery",
                  info.battery.percent === null
                    ? "Unavailable"
                    : info.battery.percent + "%",
                ],
                [
                  "Battery temperature",
                  info.battery.temperature === null
                    ? "Unavailable"
                    : info.battery.temperature + " °C",
                ],
                ["Connection", mode === "demo" ? "Simulated" : "Authorized"],
              ].map(([label, v]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            {mode === "live" && !info.mirrorAvailable && (
              <p className="hint">
                Add scrcpy to PATH and restart the console to enable screen
                control.
              </p>
            )}
            <Profile info={info} busy={busy} confirm={setPending} />
            <Security report={info.security} />
          </>
        ) : (
          <section className="empty">
            <h1>
              {busy
                ? "Reading devices…"
                : active
                  ? active.name
                  : devices.length
                    ? "Select a device"
                    : "Connect an Android device"}
            </h1>
            <p>
              {busy
                ? "Waiting for the device response."
                : active
                  ? active.state === "device"
                    ? "Refresh to read device details again."
                    : advice(active.state)
                  : devices.length
                    ? "Choose a handset from the device list to inspect it."
                    : "Connect a USB data cable, enable USB debugging on the phone and refresh."}
            </p>
          </section>
        )}
        <section className="section activity" aria-label="Session activity">
          <h2>Session activity</h2>
          <ol aria-live="polite">
            {events.length ? (
              events.map((e, i) => (
                <li key={i}>
                  <time>{e.time}</time>
                  <span>{e.message}</span>
                </li>
              ))
            ) : (
              <li className="muted">No actions in this session.</li>
            )}
          </ol>
        </section>
        <Commands commands={commands} />
        {pending && active && (
          <Confirmation
            name={active.name}
            action={pending}
            demo={mode === "demo"}
            submit={perform}
            cancel={() => setPending(null)}
          />
        )}
      </main>
    </div>
  );
}
function App() {
  const [mode, setMode] = useState<Mode>("demo");
  const [writing, setWriting] = useState(false);
  return (
    <>
      <header>
        <div className="brand">
          <img src="/favicon.svg" alt="" />
          DroidPilot
        </div>
        <span className="product">Device Control Center</span>
        <div className="modes" aria-label="Connection mode">
          {(["demo", "live"] as const).map((m) => (
            <button
              key={m}
              disabled={writing}
              aria-pressed={mode === m}
              onClick={() => setMode(m)}
            >
              {m === "demo" ? "Demo" : "ADB"}
            </button>
          ))}
        </div>
      </header>
      <div className={"banner " + mode}>
        {mode === "demo"
          ? "Demo session · Simulated device data"
          : "ADB session · Connected devices on this computer"}
      </div>
      <Workspace key={mode} mode={mode} setWriting={setWriting} />
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
