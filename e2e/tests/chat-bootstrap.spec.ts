import { test, expect } from "@playwright/test";
import { ChatPage } from "../pages/chat.page";

test.describe("Chat bootstrap", () => {
  test("loads connected session with welcome message", async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.gotoFreshSession();

    await expect(page.getByRole("heading", { name: "Tech Support AI" })).toBeVisible();
    await expect(chat.connectedBadge).toBeVisible();
    await expect(chat.conversationLog).toContainText(/support ticket/i);
    await expect(chat.messageInput).toBeEnabled();
  });
});

test.describe("Greeting flow", () => {
  test("responds to hello without creating a ticket", async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.gotoFreshSession();

    await chat.sendMessage("Hello");
    await chat.expectUserMessage("Hello");
    await chat.expectAssistantReply(/help you create or check support tickets/i);
    await expect(page.getByText("Ticket #")).not.toBeVisible();
  });
});
