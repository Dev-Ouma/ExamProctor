import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.MOODLE_URL ?? "http://localhost:8080",
    // Fake camera and auto-accepted permissions; screen share picks the whole screen.
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--auto-select-desktop-capture-source=Entire screen",
        "--enable-usermedia-screen-capturing",
      ],
    },
    permissions: ["camera"],
    trace: "retain-on-failure",
  },
});
