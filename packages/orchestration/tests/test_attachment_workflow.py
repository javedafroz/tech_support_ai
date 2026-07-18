from datetime import UTC, datetime
from uuid import uuid4

from tech_support_orchestration.models import IntentName, StructuredIntent, UserContext
from tech_support_orchestration.workflow import WorkflowEngine


def test_add_attachment_command_builds_payload():
    session_id = uuid4()
    intent = StructuredIntent(
        intent=IntentName.ADD_ATTACHMENT,
        confidence=0.9,
        session_id=session_id,
        user_id="user@test.com",
        payload={
            "ticket_number": "48228",
            "attachments": [
                {
                    "attachment_id": str(uuid4()),
                    "filename": "log.txt",
                    "mime_type": "text/plain",
                    "storage_key": "sessions/x/log.txt",
                }
            ],
            "note": "VPN logs attached",
        },
        timestamp=datetime.now(UTC),
    )
    command = WorkflowEngine().build_command(intent, UserContext(user_id="user@test.com"))
    assert command.type.value == "AddAttachment"
    assert command.payload["ticket_number"] == "48228"
    assert len(command.payload["attachments"]) == 1
