import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatShell } from "./ChatShell";

vi.mock("../../hooks/useChatSession", () => ({
  useChatSession: () => ({
    session: null,
    messages: [],
    apiOnline: false,
    loading: false,
    sending: false,
    resumed: false,
    error: "API is unavailable",
    sessionContext: null,
    detectedIntent: null,
    statusLabel: null,
    handleSend: vi.fn(),
    startNewSession: vi.fn(),
  }),
}));

describe("ChatShell", () => {
  it("shows offline state when API is unavailable", async () => {
    render(<ChatShell />);
    expect(await screen.findByText(/Offline/i)).toBeTruthy();
  });
});
