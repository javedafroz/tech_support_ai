"""Run live integration conversations using an AI User Simulator."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from tests.integration.log import (
    get_logger,
    log_scenario_end,
    log_scenario_start,
    log_turn,
    log_user_sim_note,
)
from tests.integration.scenarios import LiveTicketScenario
from tests.integration.transport import ChatTransport, SendResult
from tests.integration.user_sim import ConversationResult, ConversationTurn, OpenAIUserSimulator


def _max_turns() -> int:
    return int(os.environ.get("INTEGRATION_MAX_TURNS", "12"))


def _artifacts_dir() -> Path:
    path = Path(__file__).resolve().parent / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_stuck_loop(history: list[ConversationTurn]) -> bool:
    if len(history) < 2:
        return False
    last = history[-1].assistant_content.strip()
    prev = history[-2].assistant_content.strip()
    return bool(last and last == prev)


def _result_from_ticket(
    *,
    session_id: str,
    run_reference: str,
    transcript: list[ConversationTurn],
    turn_index: int,
    send_result: SendResult,
) -> ConversationResult:
    return ConversationResult(
        session_id=session_id,
        ticket_number=send_result.ticket_number,
        ticket_id=send_result.ticket_id,
        turns_used=turn_index,
        run_reference=run_reference,
        transcript=transcript,
        success=True,
    )


def save_transcript_artifact(result: ConversationResult, scenario_id: str) -> Path:
    filename = f"{scenario_id}_{result.run_reference}.json"
    path = _artifacts_dir() / filename
    payload = {"scenario_id": scenario_id, **result.to_artifact_dict()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    get_logger().info("Transcript saved → %s", path)
    return path


def _finalize(
    result: ConversationResult,
    scenario: LiveTicketScenario,
    *,
    mode: str,
) -> ConversationResult:
    save_transcript_artifact(result, scenario.id)
    log_scenario_end(
        scenario.id,
        success=result.success,
        ticket_number=result.ticket_number,
        turns=result.turns_used,
        reason=result.failure_reason,
    )
    return result


async def run_simulated_conversation(
    transport: ChatTransport,
    user_sim: OpenAIUserSimulator,
    *,
    scenario: LiveTicketScenario,
    user_email: str,
    max_turns: int | None = None,
    mode: str = "api",
) -> ConversationResult:
    max_turns = max_turns or _max_turns()
    run_reference = f"LIVE-{scenario.id}-{uuid4().hex[:8]}"
    transcript: list[ConversationTurn] = []

    log_scenario_start(scenario.id, run_reference, mode)
    get_logger().info("Goal: %s", scenario.user_goal)

    session_id = await transport.begin_session(user_email=user_email)
    get_logger().info("Session: %s", session_id)

    opening = await user_sim.opening_message(
        scenario, user_email=user_email, run_reference=run_reference
    )
    log_user_sim_note(opening.notes)
    user_message = opening.reply_to_support.strip()
    if not user_message:
        return _finalize(
            ConversationResult(
                session_id=session_id,
                ticket_number=None,
                ticket_id=None,
                turns_used=0,
                run_reference=run_reference,
                transcript=transcript,
                success=False,
                failure_reason="User simulator produced empty opening message",
            ),
            scenario,
            mode=mode,
        )

    for turn_index in range(1, max_turns + 1):
        send_result = await transport.send_user_message(user_message)

        transcript.append(
            ConversationTurn(
                turn_index=turn_index,
                user_message=user_message,
                assistant_content=send_result.assistant_content,
                assistant_card=send_result.assistant_card,
                detected_intent=send_result.detected_intent,
                system_statuses=send_result.system_statuses,
            )
        )
        log_turn(
            scenario_id=scenario.id,
            turn_index=turn_index,
            user_message=user_message,
            assistant_content=send_result.assistant_content,
            detected_intent=send_result.detected_intent,
            system_statuses=send_result.system_statuses,
            assistant_card=send_result.assistant_card,
        )

        if send_result.ticket_number:
            return _finalize(
                _result_from_ticket(
                    session_id=session_id,
                    run_reference=run_reference,
                    transcript=transcript,
                    turn_index=turn_index,
                    send_result=send_result,
                ),
                scenario,
                mode=mode,
            )

        active = await transport.active_ticket_number()
        if active:
            return _finalize(
                ConversationResult(
                    session_id=session_id,
                    ticket_number=str(active),
                    ticket_id=send_result.ticket_id,
                    turns_used=turn_index,
                    run_reference=run_reference,
                    transcript=transcript,
                    success=True,
                ),
                scenario,
                mode=mode,
            )

        if _is_stuck_loop(transcript):
            return _finalize(
                ConversationResult(
                    session_id=session_id,
                    ticket_number=None,
                    ticket_id=None,
                    turns_used=turn_index,
                    run_reference=run_reference,
                    transcript=transcript,
                    success=False,
                    failure_reason="Support agent repeated the same reply — possible stuck loop",
                ),
                scenario,
                mode=mode,
            )

        sim_turn = await user_sim.next_turn(
            scenario,
            user_email=user_email,
            run_reference=run_reference,
            history=transcript,
            last_assistant_content=send_result.assistant_content,
            last_assistant_card=send_result.assistant_card,
            ticket_number_on_session=str(active) if active else None,
        )
        log_user_sim_note(sim_turn.notes)

        if sim_turn.conversation_done:
            reason = sim_turn.done_reason or "unknown"
            if reason == "ticket_created" and active:
                return _finalize(
                    ConversationResult(
                        session_id=session_id,
                        ticket_number=str(active),
                        ticket_id=send_result.ticket_id,
                        turns_used=turn_index,
                        run_reference=run_reference,
                        transcript=transcript,
                        success=True,
                    ),
                    scenario,
                    mode=mode,
                )
            return _finalize(
                ConversationResult(
                    session_id=session_id,
                    ticket_number=None,
                    ticket_id=None,
                    turns_used=turn_index,
                    run_reference=run_reference,
                    transcript=transcript,
                    success=False,
                    failure_reason=(
                        f"User simulator ended conversation: {reason}. Notes: {sim_turn.notes}"
                    ),
                ),
                scenario,
                mode=mode,
            )

        user_message = sim_turn.reply_to_support.strip()
        if not user_message:
            return _finalize(
                ConversationResult(
                    session_id=session_id,
                    ticket_number=None,
                    ticket_id=None,
                    turns_used=turn_index,
                    run_reference=run_reference,
                    transcript=transcript,
                    success=False,
                    failure_reason="User simulator returned empty reply mid-conversation",
                ),
                scenario,
                mode=mode,
            )

    last_assistant = transcript[-1].assistant_content if transcript else ""
    return _finalize(
        ConversationResult(
            session_id=session_id,
            ticket_number=None,
            ticket_id=None,
            turns_used=max_turns,
            run_reference=run_reference,
            transcript=transcript,
            success=False,
            failure_reason=f"No ticket after {max_turns} turns. Last assistant: {last_assistant[:400]}",
        ),
        scenario,
        mode=mode,
    )
