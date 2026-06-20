import { describe, expect, it } from "vitest";
import { readThoughtStream } from "./streamParser";

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
}

describe("readThoughtStream", () => {
  it("parses thought and done SSE events", async () => {
    const response = streamResponse([
      'data: {"type":"thought","content":"Thinking…"}\n\n',
      'data: {"type":"done","user_message":{"id":"u1"},"assistant_message":{"id":"a1","content":"Hi"},"system_statuses":["Thinking…"],"detected_intent":null}\n\n',
    ]);

    const events = [];
    for await (const event of readThoughtStream(response)) {
      events.push(event);
    }

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: "thought", content: "Thinking…" });
    expect(events[1]?.type).toBe("done");
  });
});
