#!/usr/bin/env python3
"""Create a Zammad ticket via orchestration (Sprint 3 exit criterion).

Usage (use project venv — see README):
  .venv/bin/python scripts/create_ticket.py --dry-run ...

  export ZAMMAD_BASE_URL=https://your-zammad.example.com
  export ZAMMAD_API_TOKEN=your-token
  make create-ticket ARGS='--email john@company.com --title "VPN" --description "..."'

Optional: DATABASE_URL for audit logging to Postgres.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _in_project_venv() -> bool:
    """True when this interpreter is using the project .venv (not bare system python)."""
    try:
        return str((ROOT / ".venv").resolve()) in str(Path(sys.prefix).resolve())
    except OSError:
        return False


def _reexec_with_project_venv() -> None:
    """Re-run with project .venv when system python lacks installed packages."""
    if _in_project_venv():
        return
    venv_python = ROOT / ".venv" / "bin" / "python"
    if not venv_python.is_file():
        return
    import subprocess

    raise SystemExit(subprocess.call([str(venv_python), *sys.argv]))


_reexec_with_project_venv()

# Package paths (orchestration + zammad always; api only for live Zammad + audit)
sys.path.insert(0, str(ROOT / "packages" / "orchestration" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "zammad-client" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from tech_support_orchestration import OrchestrationEngine
from tech_support_orchestration.models import IntentName, StructuredIntent, UserContext


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


async def _maybe_audit(intent: StructuredIntent, pipeline_result) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return

    sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from tech_support_api.services.audit_service import AuditService, ZammadOperationTimer

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        audit = AuditService(db)
        await audit.record_policy(intent, pipeline_result.orchestration)
        if pipeline_result.orchestration.approved_command and pipeline_result.ticket:
            timer = ZammadOperationTimer()
            await audit.record_zammad(
                session_id=intent.session_id,
                command=pipeline_result.orchestration.approved_command,
                response=pipeline_result.ticket.model_dump(),
                status="success",
                duration_ms=timer.elapsed_ms(),
            )
    await engine.dispose()


async def main() -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Create support ticket in Zammad")
    parser.add_argument("--email", required=True, help="Customer email")
    parser.add_argument("--title", required=True, help="Ticket title")
    parser.add_argument("--description", required=True, help="Ticket description")
    parser.add_argument("--category", default="software", help="Category key (e.g. network)")
    parser.add_argument("--priority", default="normal", help="Priority key (low|normal|high)")
    parser.add_argument("--user-id", default=None, help="User id for audit (defaults to email)")
    parser.add_argument("--dry-run", action="store_true", help="Orchestration only, no Zammad call")
    args = parser.parse_args()

    session_id = uuid.uuid4()
    intent = StructuredIntent(
        intent=IntentName.CREATE_TICKET,
        confidence=0.95,
        session_id=session_id,
        user_id=args.user_id or args.email,
        payload={
            "title": args.title,
            "description": args.description,
            "customer_email": args.email,
            "suggested_category": args.category,
            "suggested_priority": args.priority,
        },
        timestamp=datetime.now(UTC),
    )
    user = UserContext(user_id=intent.user_id, email=args.email)
    mapping_path = ROOT / "config" / "zammad-field-mapping.yaml"
    engine = OrchestrationEngine.from_mapping_path(mapping_path)

    if args.dry_run:
        result = engine.process(intent, user)
        if result.outcome.value != "approved":
            print(f"REJECTED: {result.reason_code} ({result.rule_id})")
            return 1
        print("APPROVED command:")
        print(result.approved_command.model_dump_json(indent=2))
        return 0

    sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
    from tech_support_api.services.ticket_pipeline import TicketPipeline

    pipeline = TicketPipeline(mapping_path=mapping_path, orchestration=engine)
    pipeline_result = await pipeline.create_ticket_from_intent(intent, user)
    await _maybe_audit(intent, pipeline_result)

    if pipeline_result.orchestration.outcome.value != "approved":
        print(f"REJECTED: {pipeline_result.orchestration.reason_code}")
        return 1
    if pipeline_result.error:
        print(f"ZAMMAD ERROR: {pipeline_result.error}")
        return 1
    if not pipeline_result.ticket:
        print("No ticket returned")
        return 1

    ticket = pipeline_result.ticket
    print(f"Created ticket #{ticket.number} (id={ticket.id})")
    print(f"Title: {ticket.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
