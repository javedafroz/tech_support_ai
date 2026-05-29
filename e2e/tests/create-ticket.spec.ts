import { test, expect } from "@playwright/test";
import { ChatPage } from "../pages/chat.page";

const VPN_FOLLOW_UP =
  "My VPN authentication has been failing since this morning with error code 403 on corporate network.";

test.describe("Create ticket", () => {
  test("creates ticket via mock LLM and Wiremock Zammad", async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.gotoFreshSession();

    await chat.sendMessage("My VPN is not working");
    await chat.expectAssistantReply(/more detail|error message|when it started/i);

    await chat.sendMessage(VPN_FOLLOW_UP);
    await chat.expectUserMessage(VPN_FOLLOW_UP);

    await expect(page.getByText("Ticket #22042")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Network Support")).toBeVisible();
    await expect(
      page.getByLabel("Active ticket context").getByText("#22042", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/Last intent:/i)).toBeVisible();
  });
});
