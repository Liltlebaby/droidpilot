import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  use: {
    launchOptions: {
      executablePath: process.env.DROIDPILOT_TEST_BROWSER || undefined,
    },
  },
});
