from __future__ import annotations

import pytest
from tech_support_agents.nodes.respond import respond_node


@pytest.mark.asyncio
async def test_respond_prefers_ticket_created_over_stale_assistant_reply():
    out = await respond_node(
        {
            "assistant_reply": (
                "Can you tell me if you noticed any specific error messages?"
            ),
            "active_ticket_number": "48238",
            "ui_card": {
                "card_type": "ticket_created",
                "ticket_number": "48238",
                "group": "Software Support",
            },
        }
    )

    assert "48238" in out["assistant_reply"]
    assert "created your support ticket" in out["assistant_reply"].lower()
    assert "error messages" not in out["assistant_reply"].lower()


@pytest.mark.asyncio
async def test_respond_uses_assistant_reply_when_no_ticket():
    out = await respond_node(
        {"assistant_reply": "Let's try restarting your computer."}
    )
    assert out["assistant_reply"] == "Let's try restarting your computer."
