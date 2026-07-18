import styles from "./SystemStatusLine.module.css";

interface SystemStatusLineProps {
  label: string | null;
  visible: boolean;
}

export function SystemStatusLine({ label, visible }: SystemStatusLineProps) {
  if (!visible || !label) {
    return null;
  }

  return (
    <div className={styles.wrap} role="status" aria-live="polite">
      <span className={styles.spinner} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
