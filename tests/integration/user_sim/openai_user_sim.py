"""OpenAI-backed user simulator for live integration tests."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tests.integration.scenarios import LiveTicketScenario

from .prompts import build_system_prompt, build_turn_prompt
from .schema import ConversationTurn, UserSimTurn


def _format_fact_sheet(fact_sheet: dict[str, str]) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in fact_sheet.items())


class OpenAIUserSimulator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
    ) -> None:
        model = (
            model
            or os.environ.get("USER_SIM_MODEL")
            or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        )
        temperature = temperature if temperature is not None else float(
            os.environ.get("USER_SIM_TEMPERATURE", "0.4")
        )
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
        }
        if base_url:
            kwargs["base_url"] = base_url
        llm = ChatOpenAI(**kwargs)
        self._chain = llm.with_structured_output(UserSimTurn)
        self._system_prompts: dict[str, str] = {}

    def _system_prompt(
        self,
        scenario: LiveTicketScenario,
        *,
        user_email: str,
        run_reference: str,
    ) -> str:
        cache_key = f"{scenario.id}:{run_reference}"
        if cache_key not in self._system_prompts:
            self._system_prompts[cache_key] = build_system_prompt(
                user_goal=scenario.user_goal,
                persona_name=scenario.persona.name,
                persona_role=scenario.persona.role,
                persona_department=scenario.persona.department,
                user_email=user_email,
                run_reference=run_reference,
                fact_sheet_text=_format_fact_sheet(scenario.fact_sheet),
                initial_complaint_hint=scenario.initial_complaint_hint,
            )
        return self._system_prompts[cache_key]

    async def opening_message(
        self,
        scenario: LiveTicketScenario,
        *,
        user_email: str,
        run_reference: str,
    ) -> UserSimTurn:
        prompt = (
            "Generate your FIRST message to IT support about your issue. "
            "Introduce the problem naturally based on your goal and complaint hint. "
            "Do not reveal every fact sheet detail yet."
        )
        return await self._invoke(
            scenario,
            user_email=user_email,
            run_reference=run_reference,
            history=[],
            user_prompt=prompt,
            last_assistant_content="",
            last_assistant_card=None,
            ticket_number_on_session=None,
        )

    async def next_turn(
        self,
        scenario: LiveTicketScenario,
        *,
        user_email: str,
        run_reference: str,
        history: list[ConversationTurn],
        last_assistant_content: str,
        last_assistant_card: dict | None,
        ticket_number_on_session: str | None,
    ) -> UserSimTurn:
        user_prompt = build_turn_prompt(
            history=history,
            last_assistant_content=last_assistant_content,
            last_assistant_card=last_assistant_card,
            ticket_number_on_session=ticket_number_on_session,
        )
        return await self._invoke(
            scenario,
            user_email=user_email,
            run_reference=run_reference,
            history=history,
            user_prompt=user_prompt,
            last_assistant_content=last_assistant_content,
            last_assistant_card=last_assistant_card,
            ticket_number_on_session=ticket_number_on_session,
        )

    async def _invoke(
        self,
        scenario: LiveTicketScenario,
        *,
        user_email: str,
        run_reference: str,
        history: list[ConversationTurn],
        user_prompt: str,
        last_assistant_content: str,
        last_assistant_card: dict | None,
        ticket_number_on_session: str | None,
    ) -> UserSimTurn:
        messages = [
            SystemMessage(
                content=self._system_prompt(
                    scenario, user_email=user_email, run_reference=run_reference
                )
            ),
            HumanMessage(content=user_prompt),
        ]
        result = await self._chain.ainvoke(messages)
        assert isinstance(result, UserSimTurn)
        return result
