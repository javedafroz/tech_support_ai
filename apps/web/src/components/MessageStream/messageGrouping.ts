import type { ChatMessage } from "../../types/api";

export type MessageSegment =
  | { type: "message"; message: ChatMessage }
  | { type: "thoughts"; thoughts: string[] };

export function isProcessingThought(message: ChatMessage): boolean {
  return (
    message.role === "system" &&
    Boolean(message.content) &&
    !message.content!.toLowerCase().includes("continuing your conversation")
  );
}

export function groupMessages(messages: ChatMessage[]): MessageSegment[] {
  const segments: MessageSegment[] = [];
  let pendingThoughts: string[] = [];

  const flushThoughts = () => {
    if (pendingThoughts.length === 0) {
      return;
    }
    segments.push({ type: "thoughts", thoughts: [...pendingThoughts] });
    pendingThoughts = [];
  };

  for (const message of messages) {
    if (isProcessingThought(message)) {
      pendingThoughts.push(message.content!);
      continue;
    }
    flushThoughts();
    segments.push({ type: "message", message });
  }

  flushThoughts();
  return segments;
}
