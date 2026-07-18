import type { ThoughtStreamEvent } from "../types/events";

function parseEventBlock(block: string): ThoughtStreamEvent | null {
  const dataLine = block
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("data:"));
  if (!dataLine) {
    return null;
  }
  const payload = dataLine.slice(5).trim();
  if (!payload) {
    return null;
  }
  return JSON.parse(payload) as ThoughtStreamEvent;
}

export async function* readThoughtStream(
  response: Response,
): AsyncGenerator<ThoughtStreamEvent> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  if (!response.body) {
    throw new Error("Streaming response has no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = parseEventBlock(block);
      if (event) {
        yield event;
      }
    }
  }

  if (buffer.trim()) {
    const event = parseEventBlock(buffer);
    if (event) {
      yield event;
    }
  }
}
