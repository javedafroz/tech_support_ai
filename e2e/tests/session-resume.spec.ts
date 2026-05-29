import { test, expect } from "@playwright/test";
import { ChatPage } from "../pages/chat.page";

test.describe("Session persistence", () => {
  test("resumes conversation after page reload", async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.gotoFreshSession("resume-user@company.com");

    const uniqueMessage = `Session resume check ${Date.now()}`;
    await chat.sendMessage(uniqueMessage);
    await chat.expectUserMessage(uniqueMessage);
    await chat.expectAssistantReply(/./);

    await page.reload();
    await chat.waitForReady();

    await expect(page.getByText("Continuing your conversation from earlier.")).toBeVisible();
    await expect(chat.conversationLog.getByText(uniqueMessage, { exact: true })).toBeVisible();
  });

  test("starts a fresh session when New chat is clicked", async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.gotoFreshSession("new-chat-user@company.com");

    await chat.sendMessage("Hello");
    await chat.expectAssistantReply(/help you/i);

    await chat.newChatButton.click();
    await chat.waitForReady();

    await expect(page.getByText("Continuing your conversation from earlier.")).not.toBeVisible();
    await expect(chat.conversationLog).toContainText(/support ticket/i);
  });
});
