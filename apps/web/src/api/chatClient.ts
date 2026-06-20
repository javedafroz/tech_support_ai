import { readThoughtStream } from "./streamParser";
import { getStoredUserId } from "../lib/sessionStorage";
import type {
  ChatMessage,
  ChatSession,
  MessageListResponse,
  SendMessageResponse,
  SessionContextResponse,
} from "../types/api";
import type { ThoughtStreamEvent } from "../types/events";

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

export async function sendMessageStream(
  sessionId: string,
  content: string,
  onEvent: (event: ThoughtStreamEvent) => void,
): Promise<SendMessageResponse> {
  const response = await fetch(apiUrl(`/api/v1/chat/sessions/${sessionId}/messages/stream`), {
    method: "POST",
    headers: {
      ...headers(),
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ content }),
  });

  let result: SendMessageResponse | null = null;
  for await (const event of readThoughtStream(response)) {
    onEvent(event);
    if (event.type === "done") {
      result = {
        user_message: event.user_message,
        assistant_message: event.assistant_message,
        system_statuses: event.system_statuses,
        detected_intent: event.detected_intent,
      };
    }
    if (event.type === "error") {
      throw new Error(event.message);
    }
  }

  if (!result) {
    throw new Error("Thought stream ended without a final response");
  }
  return result;
}

export async function getPublicConfig(): Promise<{ thought_streaming_enabled: boolean }> {
  const response = await fetch(apiUrl("/api/v1/config/public"));
  return parseJson<{ thought_streaming_enabled: boolean }>(response);
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
