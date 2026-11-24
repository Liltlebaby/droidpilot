import { Security as Report } from "./api";

const marks = { ok: "✓", warn: "!", info: "i" };

export function Security({ report }: { report: Report | null }) {
  return (
    <section className="section" aria-labelledby="security-title">
      <h2 id="security-title">Root and boot integrity</h2>
      {report ? (
        <>
          <p
            className={
              "verdict " +
              (report.rows.some((r) => r.state === "warn") ? "warn" : "ok")
            }
          >
            {report.summary}
          </p>
          <ul className="checks">
            {report.rows.map((row) => (
              <li key={row.label} className={row.state}>
                <span className="mark" aria-hidden="true">
                  {marks[row.state]}
                </span>
                <span className="label">{row.label}</span>
                <span className="value">{row.value}</span>
              </li>
            ))}
          </ul>
          <p className="hint">
            Read-only. DroidPilot reads boot properties and looks up su and
            magisk paths. It never runs su.
          </p>
        </>
      ) : (
        <p className="hint">The device did not report its boot properties.</p>
      )}
    </section>
  );
}

export function Commands({ commands }: { commands: string[] }) {
  if (!commands.length) return null;
  return (
    <details className="section commands">
      <summary>ADB commands · last operation ({commands.length})</summary>
      <ol>
        {commands.map((command, i) => (
          <li key={i}>
            <code>$ {command}</code>
          </li>
        ))}
      </ol>
    </details>
  );
}
