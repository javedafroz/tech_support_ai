import type { Locator, Page } from "@playwright/test";
import { expect } from "@playwright/test";

export class ChatPage {
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly conversationLog: Locator;
  readonly connectedBadge: Locator;
  readonly newChatButton: Locator;

  constructor(readonly page: Page) {
    this.messageInput = page.getByLabel("Message");
    this.sendButton = page.getByRole("button", { name: "Send" });
    this.conversationLog = page.getByRole("log", { name: "Conversation" });
    this.connectedBadge = page.getByText("Connected", { exact: true });
    this.newChatButton = page.getByRole("button", { name: "New chat" });
  }

  async gotoFreshSession(userId = "e2e-user@company.com"): Promise<void> {
    await this.page.context().clearCookies();
    await this.page.goto("/");
    await this.page.evaluate((uid) => {
      localStorage.clear();
      localStorage.setItem("tech_support_user_id", uid);
    }, userId);
    await this.page.reload();
    await this.waitForReady();
  }

  async waitForReady(): Promise<void> {
    await expect(this.page.getByRole("region", { name: "Tech Support chat" })).toBeVisible();
    await expect(this.connectedBadge).toBeVisible({ timeout: 30_000 });
    await expect(this.messageInput).toBeEnabled({ timeout: 30_000 });
  }

  async sendMessage(content: string): Promise<void> {
    await this.messageInput.fill(content);
    await this.sendButton.click();
    // Composer clears input after send; wait for the turn to finish instead of Send button state.
    await expect(this.messageInput).toBeEnabled({ timeout: 30_000 });
  }

  async expectAssistantReply(matcher: RegExp | string): Promise<void> {
    await expect(this.conversationLog).toContainText(matcher, { timeout: 30_000 });
  }

  async expectUserMessage(content: string): Promise<void> {
    await expect(this.conversationLog.getByText(content, { exact: true })).toBeVisible();
  }
}
