import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../types/api";
import { MessageCard } from "./MessageCard";
import styles from "./MessageStream.module.css";

interface MessageStreamProps {
  messages: ChatMessage[];
  loading: boolean;
  sending: boolean;
  resumed?: boolean;
}

export function MessageStream({ messages, loading, sending, resumed }: MessageStreamProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, sending]);

  return (
    <div
      className={styles.stream}
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      aria-label="Conversation"
    >
      {resumed && !loading && (
        <p className={styles.system}>Continuing your conversation from earlier.</p>
      )}
      {loading && <p className={styles.system}>Starting your session…</p>}
      {!loading && messages.length === 0 && (
        <p className={styles.system}>
          Hi — I can help you create or check support tickets. Describe your issue to get started.
        </p>
      )}
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {sending && !messages.some((m) => m.role === "system") && (
        <p className={styles.typing}>Assistant is typing…</p>
      )}
      <div ref={endRef} />
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.card) {
    return (
      <div className={styles.cardWrap}>
        <MessageCard card={message.card} />
      </div>
    );
  }

  const roleClass =
    message.role === "user"
      ? styles.user
      : message.role === "assistant"
        ? styles.assistant
        : message.role === "error"
          ? styles.error
          : styles.system;

  const label =
    message.role === "user"
      ? "You"
      : message.role === "assistant"
        ? "Assistant"
        : message.role === "error"
          ? "Error"
          : "System";

  return (
    <div className={roleClass}>
      <span className={styles.label}>{label}</span>
      <p>{message.content}</p>
    </div>
  );
}
