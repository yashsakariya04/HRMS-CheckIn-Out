"""
Analytics service — aggregation queries for admin dashboard.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracker.task import TrackerTask


async def get_dashboard_stats(db: AsyncSession, org_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((TrackerTask.status == "in_progress", 1), else_=0)).label("in_progress"),
            func.sum(case((TrackerTask.status == "completed", 1), else_=0)).label("done"),
            func.sum(case((TrackerTask.status == "pending_approval", 1), else_=0)).label("pending"),
            func.sum(case((
                and_(
                    TrackerTask.deadline < now,
                    TrackerTask.status.notin_(["completed", "rejected"]),
                ), 1), else_=0,
            )).label("overdue"),
        ).where(TrackerTask.organization_id == org_id)
    )
    row = result.one()
    return {
        "total_tasks": row.total or 0,
        "in_progress": row.in_progress or 0,
        "done": row.done or 0,
        "overdue": row.overdue or 0,
        "pending": row.pending or 0,
    }
