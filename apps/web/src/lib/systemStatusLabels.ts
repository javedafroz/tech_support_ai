import type { SystemStatusLabel } from "../types/events";

/** User-facing copy per UI/UX strategy §7.3 */
export const SYSTEM_STATUS_LABELS: Record<SystemStatusLabel, string> = {
  validating: "Checking your request…",
  applying_rules: "Applying support rules…",
  creating_ticket: "Creating your ticket…",
  updating_ticket: "Updating ticket…",
  searching_tickets: "Searching your tickets…",
  uploading_attachment: "Uploading attachment…",
  queued: "Your request is queued; we'll process it shortly.",
};

export function labelForStatus(text: string): string {
  if (text in SYSTEM_STATUS_LABELS) {
    return SYSTEM_STATUS_LABELS[text as SystemStatusLabel];
  }
  return text;
}
