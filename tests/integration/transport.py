"""Chat transports for live integration — API (headless) and browser (visible).

Playwright Python uses snake_case locators: get_by_text, get_by_label, get_by_role
(not the TypeScript names getByText / getByLabel / getByRole).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from httpx import AsyncClient
from playwright.async_api import Page, expect


@dataclass
class SendResult:
    assistant_content: str
    assistant_card: dict | None
    detected_intent: str | None
    system_statuses: list[str]
    ticket_number: str | None = None
    ticket_id: int | None = None


class ChatTransport(Protocol):
    async def begin_session(self, *, user_email: str) -> str: ...

    async def send_user_message(self, content: str) -> SendResult: ...

    async def active_ticket_number(self) -> str | None: ...


def _parse_api_message_response(body: dict) -> SendResult:
    assistant = body.get("assistant_message") or {}
    card = assistant.get("card")
    ticket_number: str | None = None
    ticket_id: int | None = None
    if card and card.get("card_type") == "ticket_created":
        ticket_number = str(card.get("ticket_number", "")).strip() or None
        raw_id = card.get("ticket_id")
        ticket_id = int(raw_id) if raw_id is not None else None

    return SendResult(
        assistant_content=assistant.get("content") or "",
        assistant_card=card,
        detected_intent=body.get("detected_intent"),
        system_statuses=list(body.get("system_statuses") or []),
        ticket_number=ticket_number,
        ticket_id=ticket_id,
    )


class ApiChatTransport:
    def __init__(
        self,
        client: AsyncClient,
        *,
        headers: dict[str, str],
    ) -> None:
        self._client = client
        self._headers = headers
        self._session_id: str | None = None

    async def begin_session(self, *, user_email: str) -> str:
        del user_email
        response = await self._client.post(
            "/api/v1/chat/sessions",
            json={},
            headers=self._headers,
        )
        response.raise_for_status()
        self._session_id = response.json()["id"]
        return self._session_id

    async def send_user_message(self, content: str) -> SendResult:
        assert self._session_id
        response = await self._client.post(
            f"/api/v1/chat/sessions/{self._session_id}/messages",
            json={"content": content},
            headers=self._headers,
        )
        response.raise_for_status()
        return _parse_api_message_response(response.json())

    async def active_ticket_number(self) -> str | None:
        assert self._session_id
        response = await self._client.get(
            f"/api/v1/chat/sessions/{self._session_id}",
            headers=self._headers,
        )
        response.raise_for_status()
        return response.json().get("active_ticket_number")


class BrowserChatTransport:
    """Drives the React chat UI; captures API responses for reliable assertions."""

    def __init__(
        self,
        page: Page,
        *,
        web_url: str,
        user_email: str,
        api_base_url: str,
        api_headers: dict[str, str],
    ) -> None:
        self._page = page
        self._web_url = web_url.rstrip("/")
        self._user_email = user_email
        self._api_base_url = api_base_url.rstrip("/")
        self._api_headers = api_headers
        self._session_id: str | None = None

    async def begin_session(self, *, user_email: str) -> str:
        del user_email
        await self._page.context.clear_cookies()
        await self._page.goto(self._web_url)
        await self._page.evaluate(
            """(uid) => {
                localStorage.clear();
                localStorage.setItem('tech_support_user_id', uid);
            }""",
            self._user_email,
        )
        await self._page.reload()
        await expect(self._page.get_by_text("Connected", exact=True)).to_be_visible(timeout=30_000)
        await expect(self._page.get_by_label("Message")).to_be_enabled(timeout=30_000)

        self._session_id = await self._page.evaluate(
            "() => localStorage.getItem('tech_support_session_id')"
        )
        if not self._session_id:
            raise RuntimeError("Chat UI did not create a session (no session_id in localStorage)")
        return self._session_id

    async def send_user_message(self, content: str) -> SendResult:
        message_input = self._page.get_by_label("Message")
        send_button = self._page.get_by_role("button", name="Send")

        async with self._page.expect_response(
            lambda r: r.request.method == "POST" and "/messages" in r.url and r.ok,
            timeout=120_000,
        ) as response_info:
            await message_input.fill(content)
            await send_button.click()

        body = await (await response_info.value).json()
        await expect(message_input).to_be_enabled(timeout=120_000)
        return _parse_api_message_response(body)

    async def active_ticket_number(self) -> str | None:
        if not self._session_id:
            return None
        import httpx

        async with httpx.AsyncClient(base_url=self._api_base_url) as client:
            response = await client.get(
                f"/api/v1/chat/sessions/{self._session_id}",
                headers=self._api_headers,
            )
            response.raise_for_status()
            return response.json().get("active_ticket_number")
