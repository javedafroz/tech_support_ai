import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkApiHealth,
  createSession,
  getSession,
  getSessionContext,
  listMessages,
  sendMessage,
} from "../api/chatClient";
import {
  clearStoredSessionId,
  getStoredSessionId,
  setStoredSessionId,
} from "../lib/sessionStorage";
import type { ChatMessage, ChatSession, SessionContext } from "../types/api";

const PROCESSING_LABELS = ["Thinking…", "Checking your request…", "Applying support rules…"];

export function useChatSession() {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [resumed, setResumed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionContext, setSessionContext] = useState<SessionContext | null>(null);
  const [detectedIntent, setDetectedIntent] = useState<string | null>(null);
  const [statusLabel, setStatusLabel] = useState<string | null>(null);
  const statusTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopStatusCycle = useCallback(() => {
    if (statusTimerRef.current) {
      clearInterval(statusTimerRef.current);
      statusTimerRef.current = null;
    }
  }, []);

  const startStatusCycle = useCallback(() => {
    stopStatusCycle();
    let index = 0;
    setStatusLabel(PROCESSING_LABELS[0]);
    statusTimerRef.current = setInterval(() => {
      index = (index + 1) % PROCESSING_LABELS.length;
      setStatusLabel(PROCESSING_LABELS[index]);
    }, 450);
  }, [stopStatusCycle]);

  const loadSessionContext = useCallback(async (sessionId: string) => {
    try {
      const ctx = await getSessionContext(sessionId);
      setSessionContext(ctx.context);
    } catch {
      setSessionContext(null);
    }
  }, []);

  const loadMessages = useCallback(
    async (sessionId: string) => {
      const history = await listMessages(sessionId);
      setMessages(history);
      await loadSessionContext(sessionId);
    },
    [loadSessionContext],
  );

  useEffect(() => {
    return () => stopStatusCycle();
  }, [stopStatusCycle]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      setError(null);
      setResumed(false);

      const healthy = await checkApiHealth();
      if (cancelled) return;
      setApiOnline(healthy);
      if (!healthy) {
        setLoading(false);
        setError("API is unavailable. Start the backend and Docker services.");
        return;
      }

      try {
        const storedId = getStoredSessionId();
        let activeSession: ChatSession | null = null;

        if (storedId) {
          try {
            activeSession = await getSession(storedId);
            if (!cancelled) setResumed(true);
          } catch {
            clearStoredSessionId();
          }
        }

        if (!activeSession) {
          activeSession = await createSession();
        }

        if (cancelled) return;
        setSession(activeSession);
        setStoredSessionId(activeSession.id);
        await loadMessages(activeSession.id);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to start session");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [loadMessages]);

  const handleSend = useCallback(
    async (content: string) => {
      if (!session) return;
      setSending(true);
      setError(null);
      startStatusCycle();

      const optimistic: ChatMessage = {
        id: `optimistic-${Date.now()}`,
        session_id: session.id,
        role: "user",
        content,
        card: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimistic]);

      try {
        const result = await sendMessage(session.id, content);
        setDetectedIntent(result.detected_intent);
        if (result.system_statuses.length > 0) {
          setStatusLabel(result.system_statuses[result.system_statuses.length - 1] ?? null);
        }
        stopStatusCycle();
        await loadMessages(session.id);
        const refreshed = await getSession(session.id);
        setSession(refreshed);
      } catch (err) {
        setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
        setError(err instanceof Error ? err.message : "Failed to send message");
      } finally {
        stopStatusCycle();
        setSending(false);
        setStatusLabel(null);
      }
    },
    [session, loadMessages, startStatusCycle, stopStatusCycle],
  );

  const startNewSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResumed(false);
    setDetectedIntent(null);
    clearStoredSessionId();
    try {
      const next = await createSession();
      setSession(next);
      setStoredSessionId(next.id);
      await loadMessages(next.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setLoading(false);
    }
  }, [loadMessages]);

  return {
    session,
    messages,
    apiOnline,
    loading,
    sending,
    resumed,
    error,
    sessionContext,
    detectedIntent,
    statusLabel,
    handleSend,
    startNewSession,
  };
}
