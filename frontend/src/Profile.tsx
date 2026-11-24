import { useEffect, useRef } from "react";
import { Details, Operation } from "./api";

const rows = [
  ["Window animation", "window_animation_scale"],
  ["Transition animation", "transition_animation_scale"],
  ["Animator duration", "animator_duration_scale"],
];
const value = (n: string | null) => (n === null ? "Unset" : n + "×");

export function Profile({
  info,
  busy,
  confirm,
}: {
  info: Details;
  busy: boolean;
  confirm: (a: Operation) => void;
}) {
  return (
    <section className="section">
      <h2>Animation profile</h2>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>Animation</th>
              <th>Original</th>
              <th>Current</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, key]) => (
              <tr key={key}>
                <th scope="row">
                  {label}
                  <code>{key}</code>
                </th>
                <td>
                  {info.original ? (
                    value(info.original[key])
                  ) : (
                    <span
                      className="muted"
                      title="Backup is created on first apply"
                    >
                      —
                    </span>
                  )}
                </td>
                <td
                  className={
                    info.original && info.current[key] !== info.original[key]
                      ? "changed"
                      : ""
                  }
                >
                  {value(info.current[key])}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="actions">
        <button
          className="primary"
          disabled={busy}
          onClick={() => confirm("apply")}
        >
          Apply 0.5×
        </button>
        <button
          disabled={busy || !info.original}
          onClick={() => confirm("restore")}
        >
          Restore original
        </button>
      </div>
      <p className="hint">
        {info.original
          ? "Original values saved for this device."
          : "Original values are saved on first apply."}
      </p>
    </section>
  );
}

export function Confirmation({
  action,
  name,
  demo,
  cancel,
  submit,
}: {
  action: Operation;
  name: string;
  demo: boolean;
  cancel: () => void;
  submit: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  const labels = {
    apply: "Apply 0.5×",
    restore: "Restore original",
    mirror: "Open phone screen",
  };
  const messages = {
    apply:
      "Save the original values if needed, then set all three animation scales to 0.5×.",
    restore:
      "Write the saved profile back and verify all three settings before clearing the backup.",
    mirror: "Start a local scrcpy window to view and control this device.",
  };
  return (
    <dialog ref={ref} aria-labelledby="confirm-title" onCancel={cancel}>
      <h2 id="confirm-title">{labels[action]}</h2>
      <p>
        <strong>{name}</strong> ·{" "}
        {demo ? "Simulated device" : "Connected device"}
      </p>
      <p>{messages[action]}</p>
      <div className="actions">
        <button autoFocus onClick={cancel}>
          Cancel
        </button>
        <button className="primary" onClick={submit}>
          Confirm
        </button>
      </div>
    </dialog>
  );
}
