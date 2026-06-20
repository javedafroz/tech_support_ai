import { useEffect, useState } from "react";
import styles from "./ThoughtStreamPanel.module.css";

interface ThoughtStreamPanelProps {
  thoughts: string[];
  isLive?: boolean;
}

function collapseSummary(thoughts: string[]): string {
  if (thoughts.length === 0) {
    return "Processing…";
  }
  if (thoughts.length === 1) {
    return thoughts[0];
  }
  return `${thoughts.length} steps · ${thoughts[thoughts.length - 1]}`;
}

export function ThoughtStreamPanel({ thoughts, isLive = false }: ThoughtStreamPanelProps) {
  const [expanded, setExpanded] = useState(isLive);
  const [userToggled, setUserToggled] = useState(false);

  useEffect(() => {
    if (isLive) {
      setExpanded(true);
      setUserToggled(false);
      return;
    }
    if (!userToggled) {
      setExpanded(false);
    }
  }, [isLive, userToggled]);

  if (thoughts.length === 0) {
    return null;
  }

  const handleToggle = () => {
    setUserToggled(true);
    setExpanded((prev) => !prev);
  };

  return (
    <div className={styles.panel} data-live={isLive || undefined}>
      <button
        type="button"
        className={styles.header}
        onClick={handleToggle}
        aria-expanded={expanded}
        aria-label={expanded ? "Collapse processing steps" : "Expand processing steps"}
      >
        <span className={styles.chevron} aria-hidden="true">
          {expanded ? "▾" : "▸"}
        </span>
        <span className={styles.title}>Processing</span>
        {!expanded && <span className={styles.summary}>{collapseSummary(thoughts)}</span>}
        {isLive && <span className={styles.liveDot} aria-hidden="true" />}
      </button>
      {expanded && (
        <ol className={styles.list}>
          {thoughts.map((thought, index) => (
            <li key={`${index}-${thought}`} className={styles.item}>
              {thought}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
