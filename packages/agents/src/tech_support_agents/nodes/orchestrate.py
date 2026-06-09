from __future__ import annotations

from tech_support_orchestration import OrchestrationEngine
from tech_support_orchestration.mapping import resolve_mapping_path
from tech_support_orchestration.models import PolicyOutcome, UserContext
from tech_support_ticketing import get_ticketing_settings

from tech_support_agents.state import SupportGraphState


async def orchestrate_node(state: SupportGraphState) -> dict:
    intent = state.get("structured_intent")
    if intent is None:
        return {"error": "No structured intent to orchestrate"}

    provider = get_ticketing_settings().provider
    engine = OrchestrationEngine.from_mapping_path(resolve_mapping_path(provider))
    user = UserContext(user_id=state["user_id"], email=state.get("user_email"))
    result = engine.process(intent, user)

    statuses = list(state.get("system_statuses", []))
    statuses.append("Applying support rules…")

    updates: dict = {
        "orchestration_result": result,
        "system_statuses": statuses,
    }

    if result.outcome == PolicyOutcome.APPROVED and result.approved_command:
        updates["approved_command"] = result.approved_command
    elif result.outcome == PolicyOutcome.REJECTED:
        from tech_support_shared.reason_codes import DEFAULT_USER_MESSAGES, ReasonCode

        code = result.reason_code or ReasonCode.INTERNAL_ERROR
        try:
            message = DEFAULT_USER_MESSAGES[ReasonCode(code)]
        except ValueError:
            message = DEFAULT_USER_MESSAGES[ReasonCode.INTERNAL_ERROR]
        updates["assistant_reply"] = message
        updates["needs_clarification"] = True

    return updates
