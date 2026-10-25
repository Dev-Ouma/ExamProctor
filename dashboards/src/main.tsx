/** Entry point. report.php loads this bundle and calls ExamProctorReview.mount(element, config). */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import type { DashboardConfig } from "./api";
import { App } from "./App";
import "./review.css";

export function mount(element: HTMLElement | null, config: DashboardConfig): void {
  if (!element) return;
  element.textContent = "";
  createRoot(element).render(
    <StrictMode>
      <App config={config} />
    </StrictMode>,
  );
}
