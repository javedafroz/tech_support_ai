import type { SessionContext } from "../../types/api";
import styles from "./ContextStrip.module.css";

interface ContextStripProps {
  activeTicketNumber: string | null;
  sessionContext: SessionContext | null;
  detectedIntent: string | null;
}

export function ContextStrip({
  activeTicketNumber,
  sessionContext,
  detectedIntent,
}: ContextStripProps) {
  const messageCount = sessionContext?.message_count ?? 0;

  return (
    <div className={styles.strip} aria-label="Active ticket context">
      <div className={styles.row}>
        {activeTicketNumber ? (
          <span>
            Active ticket: <strong>#{activeTicketNumber}</strong>
          </span>
        ) : (
          <span className={styles.muted}>No active ticket</span>
        )}
        {messageCount > 0 && (
          <span className={styles.meta}>{messageCount} messages in session</span>
        )}
      </div>
      {detectedIntent && (
        <span className={styles.intent}>Last intent: {formatIntent(detectedIntent)}</span>
      )}
    </div>
  );
}

function formatIntent(intent: string): string {
  return intent.replace(/([A-Z])/g, " $1").trim();
}
