"""
Analytics service — aggregation queries for admin dashboard.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.tracker.task import TrackerTask


async def get_dashboard_stats(db: AsyncSession, org_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)

    # Total counts by status
    result = await db.execute(
        select(TrackerTask.status, func.count().label("cnt"))
        .where(TrackerTask.organization_id == org_id)
        .group_by(TrackerTask.status)
    )
    by_status = {row.status: row.cnt for row in result.all()}

    # Overdue count
    result = await db.execute(
        select(func.count()).where(
            TrackerTask.organization_id == org_id,
            TrackerTask.deadline < now,
            TrackerTask.status.notin_(["completed", "rejected"]),
        )
    )
    overdue = result.scalar() or 0

    # Bug severity distribution
    result = await db.execute(
        select(TrackerTask.severity, func.count().label("cnt"))
        .where(
            TrackerTask.organization_id == org_id,
            TrackerTask.request_type == "bug",
        )
        .group_by(TrackerTask.severity)
    )
    severity_dist = {row.severity: row.cnt for row in result.all()}

    # Per-employee productivity (assigned tasks completed vs total)
    result = await db.execute(
        select(
            Employee.id,
            Employee.full_name,
            func.count(TrackerTask.id).label("total"),
            func.sum(case((TrackerTask.status == "completed", 1), else_=0)).label("completed"),
        )
        .join(TrackerTask, TrackerTask.assigned_to == Employee.id)
        .where(TrackerTask.organization_id == org_id)
        .group_by(Employee.id, Employee.full_name)
        .order_by(func.count(TrackerTask.id).desc())
    )
    productivity = [
        {
            "employee_id": str(row.id),
            "name": row.full_name,
            "total": row.total,
            "completed": row.completed or 0,
        }
        for row in result.all()
    ]

    total = sum(by_status.values())
    return {
        "total_tasks": total,
        "by_status": by_status,
        "overdue": overdue,
        "severity_distribution": severity_dist,
        "employee_productivity": productivity,
    }
