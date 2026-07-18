import { FormEvent, useRef, useState } from "react";
import { uploadAttachment } from "../../api/chatClient";
import type { AttachmentMeta } from "../../types/api";
import styles from "./Composer.module.css";

interface ComposerProps {
  sessionId: string | null;
  onSend: (content: string, attachmentIds: string[]) => Promise<void>;
  disabled?: boolean;
}

export function Composer({ sessionId, onSend, disabled }: ComposerProps) {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState<AttachmentMeta[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if ((!trimmed && pending.length === 0) || disabled || uploading) return;
    await onSend(trimmed, pending.map((item) => item.id));
    setValue("");
    setPending([]);
    setUploadError(null);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit(event as unknown as FormEvent);
    }
  }

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files?.length || !sessionId) return;

    setUploadError(null);
    setUploading(true);
    try {
      const uploaded: AttachmentMeta[] = [];
      for (const file of Array.from(files)) {
        uploaded.push(await uploadAttachment(sessionId, file));
      }
      setPending((prev) => [...prev, ...uploaded]);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  function removePending(id: string) {
    setPending((prev) => prev.filter((item) => item.id !== id));
  }

  const canSend = Boolean((value.trim() || pending.length > 0) && !disabled && !uploading);

  return (
    <form className={styles.composer} onSubmit={(event) => void handleSubmit(event)}>
      <div className={styles.inputColumn}>
        {pending.length > 0 && (
          <ul className={styles.attachments} aria-label="Attachments to send">
            {pending.map((item) => (
              <li key={item.id} className={styles.attachmentChip}>
                <span>{item.filename}</span>
                <button
                  type="button"
                  className={styles.removeAttachment}
                  onClick={() => removePending(item.id)}
                  aria-label={`Remove ${item.filename}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {uploadError && (
          <p className={styles.uploadError} role="alert">
            {uploadError}
          </p>
        )}
        <div className={styles.inputRow}>
          <button
            type="button"
            className={styles.attach}
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading || !sessionId}
            aria-label="Attach file"
            title="Attach file"
          >
            📎
          </button>
          <input
            ref={fileInputRef}
            type="file"
            className={styles.fileInput}
            multiple
            onChange={(event) => void handleFileChange(event)}
            tabIndex={-1}
          />
          <textarea
            className={styles.input}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your issue…"
            rows={2}
            disabled={disabled || uploading}
            aria-label="Message"
          />
          <button type="submit" className={styles.send} disabled={!canSend}>
            {uploading ? "Uploading…" : "Send"}
          </button>
        </div>
      </div>
    </form>
  );
}
