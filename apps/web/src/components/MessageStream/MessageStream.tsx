import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import type { ChatMessage } from "../../types/api";
import { groupMessages } from "./messageGrouping";
import { MessageCard } from "./MessageCard";
import { ThoughtStreamPanel } from "./ThoughtStreamPanel";
import styles from "./MessageStream.module.css";
import composerStyles from "../Composer/Composer.module.css";

interface MessageStreamProps {
  messages: ChatMessage[];
  loading: boolean;
  sending: boolean;
  resumed?: boolean;
  streamedThoughts?: string[];
}

export function MessageStream({
  messages,
  loading,
  sending,
  resumed,
  streamedThoughts = [],
}: MessageStreamProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const segments = groupMessages(messages);
  const showLiveThoughts = sending && streamedThoughts.length > 0;

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, sending, streamedThoughts]);

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
      {segments.map((segment, index) => {
        if (segment.type === "thoughts") {
          return (
            <ThoughtStreamPanel
              key={`thoughts-${index}-${segment.thoughts.join("|")}`}
              thoughts={segment.thoughts}
            />
          );
        }
        return <MessageBubble key={segment.message.id} message={segment.message} />;
      })}
      {showLiveThoughts && (
        <ThoughtStreamPanel thoughts={streamedThoughts} isLive />
      )}
      {sending && streamedThoughts.length === 0 && !messages.some((m) => m.role === "system") && (
        <p className={styles.typing}>Assistant is typing…</p>
      )}
      <div ref={endRef} />
    </div>
  );
}

function MessageBody({ role, content }: { role: ChatMessage["role"]; content: string }) {
  if (role === "assistant") {
    return (
      <div className={styles.markdown}>
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    );
  }
  return <p>{content}</p>;
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const hasCard = Boolean(message.card);
  const hasContent = Boolean(message.content?.trim());

  if (hasCard) {
    const roleClass =
      message.role === "assistant"
        ? styles.assistant
        : message.role === "user"
          ? styles.user
          : styles.system;

    return (
      <div className={styles.cardGroup}>
        {hasContent && (
          <div className={roleClass}>
            <span className={styles.label}>
              {message.role === "assistant" ? "Assistant" : message.role === "user" ? "You" : "System"}
            </span>
            <MessageBody role={message.role} content={message.content!} />
          </div>
        )}
        <div className={styles.cardWrap}>
          <MessageCard card={message.card!} />
        </div>
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
      {message.content && <MessageBody role={message.role} content={message.content} />}
      {message.attachments && message.attachments.length > 0 && (
        <div className={composerStyles.messageAttachments}>
          {message.attachments.map((item) => (
            <span key={item.id} className={composerStyles.messageAttachment}>
              📎 {item.filename}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
