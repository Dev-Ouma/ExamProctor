import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App, type Mode } from "./App";

const mode: Mode = import.meta.env.VITE_EXAMPROCTOR_MODE === "live" ? "live" : "staging";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App mode={mode} />
  </StrictMode>,
);
