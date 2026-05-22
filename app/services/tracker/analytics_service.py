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
            func.sum(case((TrackerTask.status == "in_progress", 1), else_=0)).label("progress"),
            func.sum(case((TrackerTask.status == "in_development", 1), else_=0)).label("development"),
            func.sum(case((TrackerTask.status == "in_qa", 1), else_=0)).label("qa"),
            func.sum(case((TrackerTask.status == "in_stage", 1), else_=0)).label("stage"),
            func.sum(case((TrackerTask.status == "in_production", 1), else_=0)).label("done"),
            func.sum(case((TrackerTask.status == "pending_approval", 1), else_=0)).label("pending"),
            func.sum(case((
                and_(
                    TrackerTask.deadline < now,
                    TrackerTask.status.notin_(["in_production", "rejected"]),
                ), 1), else_=0,
            )).label("overdue"),
        ).where(TrackerTask.organization_id == org_id)
    )
    row = result.one()
    return {
        "total":       row.total or 0,
        "progress":    row.progress or 0,
        "development": row.development or 0,
        "qa":          row.qa or 0,
        "stage":       row.stage or 0,
        "done":        row.done or 0,
        "pending":     row.pending or 0,
        "overdue":     row.overdue or 0,
    }
