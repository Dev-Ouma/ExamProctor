/** Mounts the pre-check panel inside the Moodle preflight form. Plain DOM, no framework. */

import { ApiError, SessionApi } from "./api";
import { detectCapabilities } from "./capabilities";
import { strings, type StringKey } from "./i18n";
import { PrecheckController } from "./precheck";
import { openQueue } from "./queue";
import { ExamShell } from "./shell";

export interface MountOptions {
  container: string;
  serviceUrl: string;
  launchToken: string;
  lang: string;
  staging: boolean;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string, attrs: Record<string, string> = {}) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  return node;
}

export async function mountPrecheck(options: MountOptions): Promise<void> {
  const root = document.querySelector<HTMLElement>(options.container);
  if (!root) return;
  const t = strings(options.lang);
  const form = root.closest("form");
  const submit = form?.querySelector<HTMLInputElement | HTMLButtonElement>("[type=submit][name=submitbutton]");
  if (submit) submit.disabled = true;

  const api = new SessionApi(options.serviceUrl);
  const controller = new PrecheckController({
    api,
    media: navigator.mediaDevices,
    caps: detectCapabilities(),
  });

  root.replaceChildren();
  if (options.staging) root.append(el("div", t.staging, { class: "alert alert-warning" }));
  const message = el("div", "", { role: "status", "aria-live": "polite", class: "mt-2" });

  try {
    await controller.start(options.launchToken);
  } catch {
    root.append(el("div", t.error, { class: "alert alert-danger" }));
    return;
  }

  const consentBox = el("div", "", { class: "mb-3" });
  consentBox.append(el("h4", t.title), el("p", t.consent));
  const agree = el("button", t.agree, { type: "button", class: "btn btn-primary" });
  consentBox.append(agree);
  root.append(consentBox);

  const devices = el("div", "", { class: "mb-3", hidden: "" });
  const checkButton = el("button", t.check, { type: "button", class: "btn btn-primary mt-2", hidden: "" });
  root.append(devices, checkButton, message);

  const deviceRow = (label: StringKey, run: () => Promise<{ status: string }>) => {
    const row = el("div", "", { class: "d-flex align-items-center gap-2 mb-2" });
    const button = el("button", t[label], { type: "button", class: "btn btn-secondary" });
    const state = el("span");
    button.addEventListener("click", async () => {
      button.disabled = true;
      const result = await run();
      state.textContent = result.status === "ok" ? t.ok : t[result.status as StringKey] ?? result.status;
      button.disabled = result.status === "ok";
      checkButton.hidden = controller.pendingDevices().length > 0;
    });
    row.append(button, state);
    devices.append(row);
  };

  agree.addEventListener("click", async () => {
    agree.disabled = true;
    try {
      await controller.consent();
    } catch {
      message.textContent = t.error;
      return;
    }
    if (controller.policy.camera) deviceRow("camera", () => controller.requestCamera());
    if (controller.policy.screen && !detectCapabilities().isMobile) {
      deviceRow("screen", () => controller.requestScreen());
    }
    devices.hidden = false;
    checkButton.hidden = controller.pendingDevices().length > 0;
  });

  checkButton.addEventListener("click", async () => {
    checkButton.disabled = true;
    message.textContent = t.waiting;
    try {
      const outcome = await controller.submit();
      if (outcome.kind === "ready") {
        message.textContent = t.ready;
        if (submit) submit.disabled = false;
        const queue = await openQueue(controller.session!.session_id);
        form?.addEventListener(
          "submit",
          (event) => {
            event.preventDefault();
            new ExamShell({
              api,
              policy: controller.policy,
              queue,
              camera: controller.camera.stream,
              screen: controller.screen.stream,
              staging: options.staging,
              text: { capturing: t.capturing, screenStopped: t.screen_stopped, leaving: t.leaving, reconnecting: t.reconnecting },
            }).start(form);
          },
          { once: true },
        );
        return;
      }
      if (outcome.kind === "blocked") {
        message.replaceChildren(el("p", t.blocked));
        const list = el("ul");
        outcome.reasons.forEach((r) => list.append(el("li", t[`reason_${r}` as StringKey] ?? r)));
        message.append(list);
      } else {
        message.textContent = t.error;
      }
    } catch (error) {
      message.textContent = error instanceof ApiError ? `${t.error} (${error.code})` : t.error;
    }
    checkButton.disabled = false;
    checkButton.textContent = t.retry;
  });
}
