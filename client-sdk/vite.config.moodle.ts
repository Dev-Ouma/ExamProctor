// Builds the SDK as a UMD bundle that Moodle's RequireJS loads as `quizaccess_examproctor/sdk`.
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => {
  const minify = mode !== "src";
  return {
    build: {
      lib: {
        entry: resolve(__dirname, "src/index.ts"),
        name: "ExamProctorSDK",
        formats: ["umd"],
        fileName: () => (minify ? "sdk.min.js" : "sdk.js"),
      },
      outDir: resolve(__dirname, `../moodle/quizaccess_examproctor/amd/${minify ? "build" : "src"}`),
      emptyOutDir: false,
      minify,
      sourcemap: false,
      target: "es2020",
    },
  };
});
