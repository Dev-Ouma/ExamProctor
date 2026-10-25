/** Plain-language labels. Reviewers read these, so they describe what was seen, not guilt. */

export const FLAG_LABELS: Record<string, string> = {
  NO_FACE: "No face in camera view",
  IDENTITY_MISMATCH: "Face did not match the reference photo",
  MULTIPLE_FACES: "More than one face in view",
  ATTENTION_AWAY: "Looking away for a sustained time",
  CAMERA_OBSTRUCTED: "Camera dark or blocked",
  FOCUS_LOSS: "Left the quiz window",
  SCREEN_ALERT: "Screen content needs a look",
  AUDIO_ACTIVITY: "Speech detected",
  INPUT_ANOMALY: "Unusual typing or input pattern",
  COPY_PASTE_SEQUENCE: "Copied, left the quiz, came back and pasted",
  MULTIPLE_SCREENS: "More than one display connected",
  CONTEXT_MENU_ON_QUESTION: "Right-click on a question",
  BLANK_CAPTURE: "Blank images while capture was on",
  AUTOMATION_SUSPECTED: "Input timing unlike a person",
};

export const EVENT_LABELS: Record<string, string> = {
  shell_loaded: "Exam started",
  attempt_left: "Left the attempt (submitted or closed)",
  blur: "Quiz window lost focus",
  focus: "Quiz window focused again",
  visibility_hidden: "Quiz tab hidden",
  visibility_visible: "Quiz tab visible again",
  fullscreen_exit: "Left full screen",
  copy: "Copied text",
  cut: "Cut text",
  paste: "Pasted text",
  contextmenu: "Right-click",
  offline: "Went offline",
  online: "Back online",
  connectivity_gap: "Connection gap",
  question_shown: "Question shown",
  resize: "Window resized",
  stream_ended: "Camera or screen sharing stopped",
  display_info: "Display information",
  capture_error: "Image could not be uploaded",
};

export const DECISION_LABELS: Record<string, string> = {
  no_issue: "No issue",
  concern: "Concern noted",
  refer_misconduct: "Referred for misconduct process",
};

export const APPEAL_LABELS: Record<string, string> = {
  opened: "Appeal opened",
  upheld: "Appeal upheld",
  overturned: "Appeal overturned",
  withdrawn: "Appeal withdrawn",
};

export const BAND_LABELS: Record<string, string> = {
  clear: "Clear",
  review: "Needs review",
  high: "High priority",
  pending: "Not scored yet",
};

/** Events that matter for review; noisy ones (resize, question_shown) are still listed but muted. */
export const KEY_EVENTS = new Set([
  "blur",
  "visibility_hidden",
  "fullscreen_exit",
  "copy",
  "cut",
  "paste",
  "contextmenu",
  "offline",
  "connectivity_gap",
  "stream_ended",
  "capture_error",
  "attempt_left",
  "shell_loaded",
]);

export const label = (map: Record<string, string>, key: string | null | undefined): string =>
  key ? (map[key] ?? key.replace(/_/g, " ").toLowerCase()) : "";

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function duration(fromIso: string | null, toIso: string | null): string {
  if (!fromIso || !toIso) return "";
  const s = Math.max(0, Math.round((Date.parse(toIso) - Date.parse(fromIso)) / 1000));
  const m = Math.floor(s / 60);
  return m ? `${m} min ${s % 60} s` : `${s} s`;
}
