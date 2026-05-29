#!/usr/bin/env python3
"""Sprint 4 — Zammad sandbox smoke test (create + get ticket).

Exits 0 on success, 1 on failure. Skips when Zammad credentials are not set.

Usage:
  export ZAMMAD_BASE_URL=...
  export ZAMMAD_API_TOKEN=...
  python scripts/zammad_sandbox_e2e.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "orchestration" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "zammad-client" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from tech_support_api.services.ticket_pipeline import TicketPipeline
from tech_support_orchestration.models import IntentName, StructuredIntent, UserContext


def _credentials_present() -> bool:
    return bool(os.environ.get("ZAMMAD_BASE_URL") and os.environ.get("ZAMMAD_API_TOKEN"))


async def main() -> int:
    if not _credentials_present():
        print("SKIP: ZAMMAD_BASE_URL and ZAMMAD_API_TOKEN not set")
        return 0

    email = os.environ.get("ZAMMAD_TEST_EMAIL", "e2e-test@company.com")
    mapping_path = ROOT / "config" / "zammad-field-mapping.yaml"
    pipeline = TicketPipeline(mapping_path=mapping_path)

    intent = StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.95,
        session_id=uuid.uuid4(),
        user_id=email,
        payload={
            "title": "E2E sandbox test ticket",
            "description": "Automated Sprint 4 sandbox verification — safe to close.",
            "customer_email": email,
            "suggested_category": "software",
            "suggested_priority": "low",
        },
        timestamp=datetime.now(UTC),
    )
    user = UserContext(user_id=email, email=email)

    create_result = await pipeline.create_ticket_from_intent(intent, user)
    if not create_result.success or not create_result.ticket:
        reason = create_result.error or create_result.orchestration.reason_code
        print(f"FAIL create: {reason}")
        return 1

    ticket_id = create_result.ticket.id
    ticket_number = create_result.ticket.number
    print(f"OK created ticket #{ticket_number} (id={ticket_id})")

    fetched = await pipeline._get_zammad().get_ticket(ticket_id)
    if fetched.number != ticket_number:
        print(f"FAIL get: number mismatch {fetched.number} != {ticket_number}")
        return 1

    print(f"OK fetched ticket #{fetched.number}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
