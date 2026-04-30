"""
app/ai/context.py — User Context Builder
Builds the context dict injected into every LLM call.
Includes projects list so the LLM can map names → UUIDs without hallucinating.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.project import Project
from app.services.attendance_service import get_today_session
from app.services.balance_service import compute_realtime_balance


async def build_context(db: AsyncSession, user: Employee) -> dict:
    today_session = await get_today_session(db, user.id)
    balance = await compute_realtime_balance(db, user.id)

    # Load active projects so LLM can resolve names → UUIDs
    proj_result = await db.execute(
        select(Project).where(Project.is_active == True)
    )
    projects = [
        {"id": str(p.id), "name": p.name}
        for p in proj_result.scalars().all()
    ]

    checked_in = today_session is not None and today_session.check_out_at is None
    checked_out = today_session is not None and today_session.check_out_at is not None
    now = datetime.now(timezone.utc)

    return {
        "user_id": str(user.id),
        "name": user.full_name or user.email,
        "email": user.email,
        "role": user.role,                          # employee | admin | superadmin
        "organization_id": str(user.organization_id),
        "department_id": str(user.department_id) if user.department_id else None,
        "designation": user.designation,
        "checked_in_today": checked_in,
        "checked_out_today": checked_out,
        "check_in_at": today_session.check_in_at.strftime("%I:%M %p") if today_session else None,
        "session_id_today": str(today_session.id) if today_session else None,
        "leave_balance": {
            "casual": round(balance["casual_balance"], 2),
            "comp_off": round(balance["comp_off_balance"], 2),
        },
        "active_projects": projects,   # [{"id": "uuid", "name": "HRMS Backend"}, ...]
        "current_time": now.strftime("%I:%M %p UTC"),
        "current_date": now.strftime("%Y-%m-%d"),
    }
