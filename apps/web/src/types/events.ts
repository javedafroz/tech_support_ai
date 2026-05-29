/**
 * SSE / UI card types from packages/shared/schemas (stream-event.json, cards.json)
 */

export type SystemStatusLabel =
  | "validating"
  | "applying_rules"
  | "creating_ticket"
  | "updating_ticket"
  | "searching_tickets"
  | "uploading_attachment"
  | "queued";

export type TicketSummaryCard = {
  card_type: "ticket_summary";
  title: string;
  description: string;
  suggested_category: string;
  suggested_priority: string;
  impact?: string;
};

export type TicketCreatedCard = {
  card_type: "ticket_created";
  ticket_number: string;
  ticket_id?: number;
  group: string;
  priority: string;
  state: string;
  portal_url?: string;
};

export type TicketStatusCard = {
  card_type: "ticket_status";
  ticket_number: string;
  state: string;
  group: string;
  owner?: string;
  updated_at?: string;
};

export type DisambiguationCard = {
  card_type: "disambiguation";
  candidates: Array<{ ticket_number: string; title: string; state?: string }>;
};

export type TicketUpdatedCard = {
  card_type: "ticket_updated";
  ticket_number: string;
  message: string;
};

export type FallbackCard = {
  card_type: "fallback";
  contacts: Array<{ label: string; value: string; type?: "phone" | "email" | "url" }>;
};

export type UICard =
  | TicketSummaryCard
  | TicketCreatedCard
  | TicketStatusCard
  | DisambiguationCard
  | TicketUpdatedCard
  | FallbackCard;

export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "system_status"; label: SystemStatusLabel }
  | { type: "card"; card: UICard }
  | { type: "policy_rejected"; reason_code: string; message: string }
  | { type: "done"; message_id: string }
  | { type: "error"; code: string; message: string };
