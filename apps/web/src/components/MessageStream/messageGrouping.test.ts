import { describe, expect, it } from "vitest";
import type { ChatMessage } from "../../types/api";
import { groupMessages } from "./messageGrouping";

function message(overrides: Partial<ChatMessage>): ChatMessage {
  return {
    id: overrides.id ?? "1",
    session_id: "s1",
    role: overrides.role ?? "user",
    content: overrides.content ?? "hello",
    card: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("groupMessages", () => {
  it("groups consecutive processing system messages", () => {
    const segments = groupMessages([
      message({ id: "u1", role: "user", content: "Help" }),
      message({ id: "s1", role: "system", content: "Thinking…" }),
      message({ id: "s2", role: "system", content: "Creating ticket…" }),
      message({ id: "a1", role: "assistant", content: "Done" }),
    ]);

    expect(segments).toHaveLength(3);
    expect(segments[1]).toEqual({
      type: "thoughts",
      thoughts: ["Thinking…", "Creating ticket…"],
    });
  });
});
