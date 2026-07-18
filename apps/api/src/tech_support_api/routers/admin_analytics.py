"""Admin analytics API — conversations, deflections, and ROI summary."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tech_support_api.db.models import (
    ChatMessage,
    ChatSession,
    KbDeflectionEvent,
    KbDocument,
)
from tech_support_api.db.session import get_db
from tech_support_api.dependencies.keycloak_auth import (
    AdminPrincipal,
    require_kb_editor,
)
from tech_support_api.schemas.analytics import (
    AnalyticsSummaryResponse,
    AnalyticsTrendsResponse,
    HandbookBreakdownItem,
    SessionAnalyticsItem,
    SessionAnalyticsListResponse,
    SessionTranscriptResponse,
    TranscriptMessage,
    TrendDayItem,
)

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])

_MAX_RANGE_DAYS = 366


def _resolve_range(
    start_date: date | None,
    end_date: date | None,
    *,
    default_days: int = 30,
) -> tuple[date, date, datetime, datetime]:
    """Return (start_day, end_day, start_dt inclusive, end_dt exclusive)."""
    today = datetime.now(UTC).date()
    if start_date is None and end_date is None:
        end_day = today
        start_day = end_day - timedelta(days=default_days - 1)
    elif start_date is None:
        end_day = end_date or today
        start_day = end_day - timedelta(days=default_days - 1)
    elif end_date is None:
        start_day = start_date
        end_day = today
    else:
        start_day = start_date
        end_day = end_date

    if end_day < start_day:
        raise HTTPException(
            status_code=422,
            detail="end_date must be on or after start_date",
        )
    if (end_day - start_day).days + 1 > _MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"Date range cannot exceed {_MAX_RANGE_DAYS} days",
        )

    start_dt = datetime.combine(start_day, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=UTC)
    return start_day, end_day, start_dt, end_dt


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def analytics_summary(
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> AnalyticsSummaryResponse:
    del principal
    _, _, start_dt, end_dt = _resolve_range(start_date, end_date)

    session_in_range = (
        ChatSession.created_at >= start_dt,
        ChatSession.created_at < end_dt,
    )
    message_in_range = (
        ChatMessage.created_at >= start_dt,
        ChatMessage.created_at < end_dt,
    )
    event_in_range = (
        KbDeflectionEvent.created_at >= start_dt,
        KbDeflectionEvent.created_at < end_dt,
    )

    total_conversations = int(
        (
            await db.execute(
                select(func.count()).select_from(ChatSession).where(*session_in_range)
            )
        ).scalar_one()
    )
    total_messages = int(
        (
            await db.execute(
                select(func.count()).select_from(ChatMessage).where(*message_in_range)
            )
        ).scalar_one()
    )
    tickets_created = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ChatSession)
                .where(
                    *session_in_range,
                    ChatSession.active_ticket_number.is_not(None),
                )
            )
        ).scalar_one()
    )
    deflections_resolved = int(
        (
            await db.execute(
                select(func.count())
                .select_from(KbDeflectionEvent)
                .where(*event_in_range, KbDeflectionEvent.outcome == "resolved")
            )
        ).scalar_one()
    )
    deflections_escalated = int(
        (
            await db.execute(
                select(func.count())
                .select_from(KbDeflectionEvent)
                .where(*event_in_range, KbDeflectionEvent.outcome == "escalated")
            )
        ).scalar_one()
    )
    denom = deflections_resolved + deflections_escalated
    deflection_rate = (deflections_resolved / denom) if denom else 0.0

    breakdown_rows = (
        await db.execute(
            select(
                KbDeflectionEvent.document_id,
                func.coalesce(KbDocument.title, "Unknown handbook").label("title"),
                func.coalesce(
                    func.sum(case((KbDeflectionEvent.outcome == "resolved", 1), else_=0)),
                    0,
                ).label("resolved"),
                func.coalesce(
                    func.sum(case((KbDeflectionEvent.outcome == "escalated", 1), else_=0)),
                    0,
                ).label("escalated"),
            )
            .outerjoin(KbDocument, KbDocument.id == KbDeflectionEvent.document_id)
            .where(*event_in_range)
            .group_by(KbDeflectionEvent.document_id, KbDocument.title)
            .order_by(func.count().desc())
        )
    ).all()

    by_handbook = [
        HandbookBreakdownItem(
            document_id=row.document_id,
            title=str(row.title),
            resolved=int(row.resolved),
            escalated=int(row.escalated),
        )
        for row in breakdown_rows
    ]

    return AnalyticsSummaryResponse(
        total_conversations=total_conversations,
        total_messages=total_messages,
        tickets_created=tickets_created,
        deflections_resolved=deflections_resolved,
        deflections_escalated=deflections_escalated,
        deflection_rate=round(deflection_rate, 4),
        by_handbook=by_handbook,
    )


@router.get("/trends", response_model=AnalyticsTrendsResponse)
async def analytics_trends(
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=90),
) -> AnalyticsTrendsResponse:
    del principal
    if days is not None and start_date is None and end_date is None:
        start_day, end_day, start_dt, end_dt = _resolve_range(None, None, default_days=days)
    else:
        start_day, end_day, start_dt, end_dt = _resolve_range(
            start_date, end_date, default_days=days or 30
        )

    session_day = cast(ChatSession.created_at, Date).label("day")
    session_rows = (
        await db.execute(
            select(session_day, func.count().label("count"))
            .where(ChatSession.created_at >= start_dt, ChatSession.created_at < end_dt)
            .group_by(session_day)
        )
    ).all()
    sessions_by_day = {row.day: int(row.count) for row in session_rows}

    event_day = cast(KbDeflectionEvent.created_at, Date).label("day")
    event_rows = (
        await db.execute(
            select(
                event_day,
                func.coalesce(
                    func.sum(case((KbDeflectionEvent.outcome == "resolved", 1), else_=0)),
                    0,
                ).label("resolved"),
                func.coalesce(
                    func.sum(case((KbDeflectionEvent.outcome == "escalated", 1), else_=0)),
                    0,
                ).label("escalated"),
            )
            .where(
                KbDeflectionEvent.created_at >= start_dt,
                KbDeflectionEvent.created_at < end_dt,
            )
            .group_by(event_day)
        )
    ).all()
    events_by_day = {
        row.day: (int(row.resolved), int(row.escalated)) for row in event_rows
    }

    items: list[TrendDayItem] = []
    cursor: date = start_day
    while cursor <= end_day:
        resolved, escalated = events_by_day.get(cursor, (0, 0))
        items.append(
            TrendDayItem(
                date=cursor.isoformat(),
                conversations=sessions_by_day.get(cursor, 0),
                resolved=resolved,
                escalated=escalated,
            )
        )
        cursor += timedelta(days=1)

    return AnalyticsTrendsResponse(days=len(items), items=items)


@router.get("/sessions", response_model=SessionAnalyticsListResponse)
async def list_sessions(
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> SessionAnalyticsListResponse:
    del principal
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    _, _, start_dt, end_dt = _resolve_range(start_date, end_date)

    session_filter = (
        ChatSession.created_at >= start_dt,
        ChatSession.created_at < end_dt,
    )

    total = int(
        (
            await db.execute(
                select(func.count()).select_from(ChatSession).where(*session_filter)
            )
        ).scalar_one()
    )

    ranked = (
        select(
            KbDeflectionEvent.id.label("event_id"),
            KbDeflectionEvent.session_id.label("session_id"),
            KbDeflectionEvent.outcome.label("outcome"),
            KbDeflectionEvent.steps_count.label("steps_count"),
            KbDeflectionEvent.document_id.label("document_id"),
            func.row_number()
            .over(
                partition_by=KbDeflectionEvent.session_id,
                order_by=KbDeflectionEvent.created_at.desc(),
            )
            .label("rn"),
        )
    ).subquery()
    latest = select(ranked).where(ranked.c.rn == 1).subquery()

    message_count = (
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.session_id == ChatSession.id)
        .correlate(ChatSession)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            ChatSession,
            message_count.label("message_count"),
            latest.c.outcome,
            latest.c.steps_count,
            latest.c.document_id,
            KbDocument.title,
        )
        .where(*session_filter)
        .outerjoin(latest, latest.c.session_id == ChatSession.id)
        .outerjoin(KbDocument, KbDocument.id == latest.c.document_id)
        .order_by(ChatSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()

    items = [
        SessionAnalyticsItem(
            id=session.id,
            user_id=session.user_id,
            org_id=session.org_id,
            status=session.status,
            active_ticket_number=session.active_ticket_number,
            message_count=int(msg_count or 0),
            deflection_outcome=outcome,
            deflection_steps_count=int(steps_count) if steps_count is not None else None,
            handbook_document_id=document_id,
            handbook_title=handbook_title,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        for session, msg_count, outcome, steps_count, document_id, handbook_title in rows
    ]
    return SessionAnalyticsListResponse(items=items, total=total)


@router.get("/sessions/{session_id}/messages", response_model=SessionTranscriptResponse)
async def session_transcript(
    session_id: UUID,
    principal: AdminPrincipal = Depends(require_kb_editor),
    db: AsyncSession = Depends(get_db),
) -> SessionTranscriptResponse:
    del principal
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.seq.asc())
    )
    messages = list(result.scalars().all())
    return SessionTranscriptResponse(
        session_id=session_id,
        messages=[TranscriptMessage.model_validate(m) for m in messages],
    )
