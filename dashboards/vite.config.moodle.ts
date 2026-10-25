// Builds the reviewer dashboard as one IIFE script plus a stylesheet for local_examproctor/report.php.
// IIFE, not UMD: Moodle pages load RequireJS, and a UMD bundle would register as an anonymous AMD module.
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    lib: {
      entry: resolve(import.meta.dirname, "src/main.tsx"),
      name: "ExamProctorReview",
      formats: ["iife"],
      fileName: () => "review.js",
      cssFileName: "review",
    },
    outDir: resolve(import.meta.dirname, "../moodle/local_examproctor/dashboard"),
    emptyOutDir: true,
    sourcemap: false,
    target: "es2020",
  },
});
