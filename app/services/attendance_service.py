from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.attendance_session import AttendanceSession
from app.models.task_entry import TaskEntry
from app.schemas.attendance import CheckInRequest
from sqlalchemy.orm import joinedload

async def get_today_session(db: AsyncSession, employee_id) -> Optional[AttendanceSession]:
    today = date.today()
    result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.session_date == today,
        )
    )
    return result.scalars().first()


async def check_in(db: AsyncSession, employee_id, organization_id, body: CheckInRequest) -> AttendanceSession:
    existing = await get_today_session(db, employee_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already checked in today.")

    if not body.tasks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one task is required to check in.")

    now = datetime.now(timezone.utc)
    session = AttendanceSession(
        employee_id=employee_id,
        organization_id=organization_id,
        session_date=date.today(),
        check_in_at=now,
        work_mode="office",
        is_corrected=False,
    )
    db.add(session)
    await db.flush()

    for task in body.tasks:
        db.add(TaskEntry(
            session_id=session.id,
            project_id=task.project_id,
            employee_id=employee_id,
            description=task.description,
            hours_logged=task.hours,
        ))

    await db.commit()
    await db.refresh(session)
    return session


async def check_out(db: AsyncSession, employee_id) -> AttendanceSession:
    session = await get_today_session(db, employee_id)

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session found. Please check in first.")

    if session.check_out_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already checked out today.")

    now = datetime.now(timezone.utc)
    session.check_out_at = now

    check_in = session.check_in_at
    if check_in.tzinfo is None:
        check_in = check_in.replace(tzinfo=timezone.utc)
    session.total_hours = round((now - check_in).total_seconds() / 3600, 2)

    await db.commit()
    await db.refresh(session)
    return session


async def get_sessions_for_month(db: AsyncSession, employee_id, month: int, year: int) -> list:
    result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.employee_id == employee_id,
            extract("month", AttendanceSession.session_date) == month,
            extract("year", AttendanceSession.session_date) == year,
        ).order_by(AttendanceSession.session_date.desc())
    )
    sessions = result.scalars().all()

    output = []
    for s in sessions:
        # tasks_result = await db.execute(
        #     select(TaskEntry).where(TaskEntry.session_id == s.id).order_by(TaskEntry.sort_order)
        # )
        tasks_result = await db.execute(
            select(TaskEntry)
            .options(joinedload(TaskEntry.project))
            .where(TaskEntry.session_id == s.id)
            .order_by(TaskEntry.sort_order)
        )
        tasks = tasks_result.scalars().all()
        task_list = [
            {
                "id": t.id,
                "description": t.description,
                "hours_logged": float(t.hours_logged),
                "project_id": t.project_id,
                "project_name": t.project.name if t.project else "",
            }
            for t in tasks
        ]
        output.append({
            "id": s.id,
            "session_date": s.session_date,
            "check_in_at": s.check_in_at,
            "check_out_at": s.check_out_at,
            "total_hours": float(s.total_hours) if s.total_hours else None,
            "work_mode": s.work_mode,
            "is_corrected": s.is_corrected,
            "tasks": task_list,
            "tasks_summary": ", ".join(t["description"] for t in task_list),
        })
    return output


def generate_csv(sessions: list) -> str:
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Reporting task", "Check in time", "Check out time", "Total hours"])
    for s in sessions:
        writer.writerow([
            s["session_date"].strftime("%d-%m-%Y"),
            s["tasks_summary"],
            s["check_in_at"].strftime("%I:%M %p"),
            s["check_out_at"].strftime("%I:%M %p") if s["check_out_at"] else "—",
            f"{s['total_hours']:.2f}" if s["total_hours"] is not None else "—",
        ])
    return output.getvalue()
