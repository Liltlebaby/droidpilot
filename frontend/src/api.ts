export type Mode = "demo" | "live";
export type Operation = "apply" | "restore" | "mirror";
export type Device = { id: string; name: string; state: string };
export type Scales = Record<string, string | null>;
export type Details = {
  model: string;
  android_version: string;
  current: Scales;
  original: Scales | null;
  battery: { percent: number | null; temperature: number | null };
  mirrorAvailable: boolean;
};
const token = document.querySelector<HTMLMetaElement>(
  'meta[name="droidpilot-session"]',
)!.content;
export async function request<T>(
  mode: Mode,
  action: string,
  device?: string,
  confirmed = false,
): Promise<T> {
  const response = await fetch("/api/device", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-DroidPilot-Session": token,
    },
    body: JSON.stringify({ mode, action, device, confirmed }),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.error || "Request failed. Refresh the session.");
  return result as T;
}
