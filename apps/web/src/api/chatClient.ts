import { getStoredUserId } from "../lib/sessionStorage";
import type {
  ChatMessage,
  ChatSession,
  MessageListResponse,
  SendMessageResponse,
  SessionContextResponse,
} from "../types/api";

const USER_HEADER = "X-User-Id";

/** Empty = same-origin (Vite dev proxy). Set in Docker to http://localhost:8000. */
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function headers(): HeadersInit {
  return {
    "Content-Type": "application/json",
    [USER_HEADER]: getStoredUserId(),
  };
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

export async function createSession(): Promise<ChatSession> {
  const response = await fetch(apiUrl("/api/v1/chat/sessions"), {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({}),
  });
  return parseJson<ChatSession>(response);
}

export async function getSession(sessionId: string): Promise<ChatSession> {
  const response = await fetch(apiUrl(`/api/v1/chat/sessions/${sessionId}`), {
    headers: headers(),
  });
  return parseJson<ChatSession>(response);
}

export async function listMessages(sessionId: string): Promise<ChatMessage[]> {
  const response = await fetch(apiUrl(`/api/v1/chat/sessions/${sessionId}/messages`), {
    headers: headers(),
  });
  const data = await parseJson<MessageListResponse>(response);
  return data.messages;
}

export async function sendMessage(
  sessionId: string,
  content: string,
): Promise<SendMessageResponse> {
  const response = await fetch(apiUrl(`/api/v1/chat/sessions/${sessionId}/messages`), {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ content }),
  });
  return parseJson<SendMessageResponse>(response);
}

export async function getSessionContext(sessionId: string): Promise<SessionContextResponse> {
  const response = await fetch(apiUrl(`/api/v1/chat/sessions/${sessionId}/context`), {
    headers: headers(),
  });
  return parseJson<SessionContextResponse>(response);
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(apiUrl("/health/live"));
    return response.ok;
  } catch {
    return false;
  }
}
