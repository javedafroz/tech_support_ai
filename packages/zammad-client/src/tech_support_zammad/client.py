from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import httpx

from tech_support_zammad.errors import ZammadError, ZammadErrorCode
from tech_support_zammad.models import CreateTicketRequest, Ticket, TicketSearchResult


class ZammadClient:
    RETRYABLE_STATUS = {502, 503, 504}
    MAX_RETRIES = 3

    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        auth_scheme: str = "Bearer",
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_scheme = auth_scheme
        self._timeout = timeout
        self._headers = {
            "Authorization": self._format_auth(api_token),
            "Content-Type": "application/json",
        }

    @staticmethod
    def _format_auth(token: str) -> str:
        if token.lower().startswith("bearer ") or token.lower().startswith("token "):
            return token
        return f"Bearer {token}"

    def _map_error(self, response: httpx.Response) -> ZammadError:
        status = response.status_code
        body = response.text[:500]
        if status in (401, 403):
            return ZammadError(
                ZammadErrorCode.AUTH_FAILED,
                body or "Authentication failed",
                status_code=status,
            )
        if status == 404:
            return ZammadError(
                ZammadErrorCode.NOT_FOUND,
                body or "Not found",
                status_code=status,
            )
        if status == 422:
            return ZammadError(
                ZammadErrorCode.VALIDATION_ERROR,
                body or "Validation error",
                status_code=status,
            )
        if status == 429:
            return ZammadError(
                ZammadErrorCode.RATE_LIMITED,
                body or "Rate limited",
                status_code=status,
            )
        if status in self.RETRYABLE_STATUS:
            return ZammadError(
                ZammadErrorCode.UNAVAILABLE,
                body or "Service unavailable",
                status_code=status,
            )
        return ZammadError(
            ZammadErrorCode.UNKNOWN,
            body or "Unknown Zammad error",
            status_code=status,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: UUID | None = None,
    ) -> Any:
        headers = dict(self._headers)
        if idempotency_key:
            headers["Idempotency-Key"] = str(idempotency_key)

        last_error: ZammadError | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout,
                ) as client:
                    response = await client.request(
                        method,
                        path,
                        headers=headers,
                        json=json,
                        params=params,
                    )
            except httpx.TimeoutException as exc:
                last_error = ZammadError(ZammadErrorCode.TIMEOUT, "Zammad request timed out")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise last_error from exc
            except httpx.HTTPError as exc:
                raise ZammadError(ZammadErrorCode.UNAVAILABLE, str(exc)) from exc

            if response.is_success:
                if response.status_code == 204:
                    return None
                return response.json()

            err = self._map_error(response)
            if err.code == ZammadErrorCode.UNAVAILABLE and attempt < self.MAX_RETRIES - 1:
                last_error = err
                await asyncio.sleep(2**attempt)
                continue
            raise err

        if last_error:
            raise last_error
        raise ZammadError(ZammadErrorCode.UNKNOWN, "Request failed")

    async def create_ticket(
        self,
        request: CreateTicketRequest,
        *,
        idempotency_key: UUID | None = None,
    ) -> Ticket:
        payload = request.model_dump(exclude_none=True)
        data = await self._request(
            "POST",
            "/api/v1/tickets",
            json=payload,
            idempotency_key=idempotency_key,
        )
        return Ticket.model_validate(data)

    async def get_ticket(self, ticket_id: int) -> Ticket:
        data = await self._request("GET", f"/api/v1/tickets/{ticket_id}")
        return Ticket.model_validate(data)

    async def search_tickets(self, query: str, *, limit: int = 10) -> TicketSearchResult:
        data = await self._request(
            "GET",
            "/api/v1/tickets/search",
            params={"query": query, "limit": limit},
        )
        if isinstance(data, list):
            tickets = [Ticket.model_validate(item) for item in data]
            return TicketSearchResult(tickets=tickets, count=len(tickets))
        tickets_raw = data.get("tickets", data) if isinstance(data, dict) else []
        tickets = [Ticket.model_validate(item) for item in tickets_raw]
        count = data.get("count", len(tickets)) if isinstance(data, dict) else len(tickets)
        return TicketSearchResult(tickets=tickets, count=int(count))
