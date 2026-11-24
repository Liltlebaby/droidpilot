import { test as base, expect } from "@playwright/test";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { resolve } from "node:path";
import { createInterface } from "node:readline";

export const test = base.extend<{}, { consoleURL: string }>({
  consoleURL: [
    async ({}, use) => {
      // Own the Python child directly so teardown works without shell process-tree utilities on Windows.
      const child = spawn(
        "python",
        ["-u", "-m", "droidpilot", "dashboard", "--no-browser", "--port", "0"],
        {
          env: { ...process.env, PYTHONPATH: resolve("../src") },
          stdio: ["ignore", "pipe", "inherit"],
        },
      );
      const lines = createInterface({ input: child.stdout });
      const closed = once(child, "close");
      try {
        const [line] = await Promise.race([
          once(lines, "line"),
          closed.then(() => {
            throw new Error("Dashboard exited before announcing its URL.");
          }),
        ]);
        const url = /http:\/\/127\.0\.0\.1:\d+/.exec(String(line))?.[0];
        if (!url) throw new Error("Dashboard did not print a loopback URL.");
        await use(url);
      } finally {
        lines.close();
        child.kill();
        await closed;
      }
    },
    { scope: "worker" },
  ],
  baseURL: async ({ consoleURL }, use) => use(consoleURL),
});
export { expect };
