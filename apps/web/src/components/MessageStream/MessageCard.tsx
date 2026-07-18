import type { UICard } from "../../types/events";
import styles from "./MessageCard.module.css";

interface MessageCardProps {
  card: Record<string, unknown>;
}

function isCard(value: Record<string, unknown>): value is UICard & Record<string, unknown> {
  return typeof value.card_type === "string";
}

export function MessageCard({ card }: MessageCardProps) {
  if (!isCard(card)) {
    return null;
  }

  switch (card.card_type) {
    case "ticket_created":
      return (
        <div className={styles.card}>
          <strong>Ticket #{card.ticket_number}</strong>
          <p>
            {card.group} · {card.priority} · {card.state}
          </p>
        </div>
      );
    case "ticket_status":
      return (
        <div className={styles.card}>
          <strong>#{card.ticket_number}</strong>
          <p>
            {card.state} · {card.group}
          </p>
        </div>
      );
    case "ticket_summary":
      return (
        <div className={styles.card}>
          <strong>{card.title}</strong>
          <p>{card.description}</p>
        </div>
      );
    default:
      return (
        <div className={styles.card}>
          <pre className={styles.raw}>{JSON.stringify(card, null, 2)}</pre>
        </div>
      );
  }
}
