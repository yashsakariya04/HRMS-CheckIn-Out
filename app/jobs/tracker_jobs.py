"""
Tracker background jobs:
  1. deadline_reminder  — daily, notifies employees whose tasks are due within 24h
  2. overdue_flagging   — daily, logs overdue activity for tasks past deadline
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_

from app.dependencies.database import AsyncSessionLocal
from app.models.tracker.task import TrackerTask
from app.services.tracker.activity_service import log_activity
from app.services.tracker.notification_service import notify


async def run_deadline_reminders():
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        window = now + timedelta(hours=24)
        result = await db.execute(
            select(TrackerTask).where(
                and_(
                    TrackerTask.deadline >= now,
                    TrackerTask.deadline <= window,
                    TrackerTask.status.notin_(["completed", "rejected"]),
                    TrackerTask.assigned_to.isnot(None),
                )
            )
        )
        tasks = result.scalars().all()
        for task in tasks:
            await notify(
                db, task.assigned_to,
                "Deadline Approaching",
                f"Task '{task.title}' is due within 24 hours",
                task.id,
            )
        await db.commit()


async def run_overdue_flagging():
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(TrackerTask).where(
                and_(
                    TrackerTask.deadline < now,
                    TrackerTask.status.notin_(["completed", "rejected"]),
                    TrackerTask.assigned_to.isnot(None),
                )
            )
        )
        tasks = result.scalars().all()
        for task in tasks:
            await log_activity(
                db, task.id, "overdue_flagged",
                f"Task is overdue (deadline was {task.deadline.strftime('%Y-%m-%d %H:%M UTC')})",
            )
            await notify(
                db, task.assigned_to,
                "Task Overdue",
                f"Task '{task.title}' is past its deadline",
                task.id,
            )
        await db.commit()
