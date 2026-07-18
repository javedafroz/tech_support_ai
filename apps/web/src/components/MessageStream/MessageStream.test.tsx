import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ChatMessage } from "../../types/api";
import { MessageStream } from "./MessageStream";

function assistantMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "a1",
    session_id: "s1",
    role: "assistant",
    content: "I've created your support ticket #48228.",
    card: {
      card_type: "ticket_created",
      ticket_number: "48228",
      group: "Network Support",
      priority: "3 high",
      state: "open",
    },
    created_at: "2026-05-23T00:00:00.000Z",
    ...overrides,
  };
}

describe("MessageStream", () => {
  it("shows concluding assistant text above the ticket card", () => {
    render(
      <MessageStream
        messages={[assistantMessage()]}
        loading={false}
        sending={false}
      />,
    );

    expect(
      screen.getByText("I've created your support ticket #48228."),
    ).toBeTruthy();
    expect(screen.getByText(/Ticket #48228/)).toBeTruthy();
  });

  it("still renders card-only messages when no text is present", () => {
    render(
      <MessageStream
        messages={[assistantMessage({ content: "" })]}
        loading={false}
        sending={false}
      />,
    );

    expect(screen.getByText(/Ticket #48228/)).toBeTruthy();
    expect(screen.queryByText("Assistant")).toBeNull();
  });

  it("renders markdown lists and emphasis in assistant messages", () => {
    render(
      <MessageStream
        messages={[
          assistantMessage({
            content:
              "From the guide, let's try this step:\n\n**Step 1: Restart**\n\n1. Save all work.\n2. Click Restart.\n\nLet me know if it worked.",
            card: undefined,
          }),
        ]}
        loading={false}
        sending={false}
      />,
    );

    expect(screen.getByText("Step 1: Restart").tagName).toBe("STRONG");
    expect(screen.getByText("Save all work.").closest("li")).toBeTruthy();
    expect(screen.getByText("Click Restart.").closest("li")).toBeTruthy();
  });
});
