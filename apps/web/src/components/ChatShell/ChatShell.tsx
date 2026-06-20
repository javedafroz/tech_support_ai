import { useChatSession } from "../../hooks/useChatSession";
import { Composer } from "../Composer/Composer";
import { ContextStrip } from "../ContextStrip/ContextStrip";
import { MessageStream } from "../MessageStream/MessageStream";
import { SystemStatusLine } from "../SystemStatusLine/SystemStatusLine";
import styles from "./ChatShell.module.css";

export function ChatShell() {
  const {
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
    streamedThoughts,
    useThoughtStreaming,
    handleSend,
    startNewSession,
  } = useChatSession();

  return (
    <div className={styles.shell} role="region" aria-label="Tech Support chat">
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>Tech Support AI</h1>
          <p className={styles.subtitle}>
            Powered by AI · Ticket actions are recorded in your organization&apos;s support system
          </p>
        </div>
        <div className={styles.headerActions}>
          <span
            className={apiOnline ? styles.badgeOk : styles.badgeWarn}
            aria-live="polite"
          >
            {apiOnline === null ? "…" : apiOnline ? "Connected" : "Offline"}
          </span>
          <button
            type="button"
            className={styles.newChat}
            onClick={startNewSession}
            disabled={loading || sending}
          >
            New chat
          </button>
        </div>
      </header>

      <ContextStrip
        activeTicketNumber={session?.active_ticket_number ?? null}
        sessionContext={sessionContext}
        detectedIntent={detectedIntent}
      />

      <SystemStatusLine
        label={statusLabel}
        visible={sending && (!useThoughtStreaming || Boolean(statusLabel))}
      />

      <MessageStream
        messages={messages}
        loading={loading}
        sending={sending}
        resumed={resumed}
        streamedThoughts={streamedThoughts}
      />

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <Composer onSend={handleSend} disabled={!session || sending || loading} />
    </div>
  );
}
