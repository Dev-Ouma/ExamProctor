import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/", "vite.config.moodle.ts", "vitest.config.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
);
