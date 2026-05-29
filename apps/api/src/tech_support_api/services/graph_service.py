from __future__ import annotations

from tech_support_agents.runner import SupportGraphRunner
from tech_support_api.config import get_settings

_runner: SupportGraphRunner | None = None


def get_graph_runner() -> SupportGraphRunner:
    global _runner
    if _runner is None:
        _runner = SupportGraphRunner.compile()
    return _runner


async def init_graph_runner() -> None:
    """Optional Postgres checkpointer setup (call from app lifespan)."""
    global _runner
    settings = get_settings()
    if not settings.graph_enabled or not settings.graph_checkpoint:
        return

    from tech_support_agents.checkpoint import postgres_checkpointer

    checkpointer_cm = postgres_checkpointer(settings.database_url_sync)
    checkpointer = await checkpointer_cm.__aenter__()
    _runner = SupportGraphRunner.compile(checkpointer=checkpointer)


def is_graph_enabled() -> bool:
    return get_settings().graph_enabled
