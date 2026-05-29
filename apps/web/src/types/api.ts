/**
 * API types aligned with FastAPI schemas (Sprint 2).
 * Source of truth: apps/api schemas + packages/shared/schemas/*.json
 */

export type MessageRole = "user" | "assistant" | "system" | "error";

export interface ChatSession {
  id: string;
  user_id: string;
  org_id: string | null;
  status: string;
  active_ticket_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionContext {
  active_ticket_number: string | null;
  last_message_at: string | null;
  message_count: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string | null;
  card: Record<string, unknown> | null;
  created_at: string;
}

export interface MessageListResponse {
  messages: ChatMessage[];
  total: number;
  limit: number;
  offset: number;
}

export interface SendMessageResponse {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  system_statuses: string[];
  detected_intent: string | null;
}

export interface SessionListResponse {
  sessions: ChatSession[];
}

export interface SessionContextResponse {
  session_id: string;
  context: SessionContext | null;
}
