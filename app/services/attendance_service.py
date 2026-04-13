"""
app/services/attendance_service.py — Attendance Business Logic
==============================================================
Handles check-in, check-out, session retrieval, and CSV generation.

Non-technical summary:
----------------------
This service manages the core attendance workflow:
  - Check-in  : Creates a new session for today with the employee's tasks.
  - Check-out : Closes the session and calculates total hours worked.
  - Sessions  : Retrieves historical sessions with their tasks for a given month.
  - CSV       : Generates a downloadable attendance report.

Business rules enforced here:
  - An employee can only check in once per day.
  - At least one task must be provided at check-in.
  - Checkout time is always after check-in time.
  - Total hours = (checkout - checkin) in decimal hours.
"""

import csv
import io
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.attendance_session import AttendanceSession
from app.models.task_entry import TaskEntry
from app.schemas.attendance import CheckInRequest


async def get_today_session(db: AsyncSession, employee_id) -> Optional[AttendanceSession]:
    """
    Return today's attendance session for the given employee, or None.

    Args:
        db:          Async database session.
        employee_id: UUID of the employee.
    """
    today = date.today()
    result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.session_date == today,
        )
    )
    return result.scalars().first()


async def check_in(
    db: AsyncSession, employee_id, organization_id, body: CheckInRequest
) -> AttendanceSession:
    """
    Check in the employee for today and create their initial task entries.

    Steps:
      1. Verify no session exists for today (prevent double check-in).
      2. Validate at least one task is provided.
      3. Create the AttendanceSession record.
      4. Create TaskEntry records for each task in the request.

    Args:
        db:              Async database session.
        employee_id:     UUID of the employee checking in.
        organization_id: UUID of the employee's organization.
        body:            CheckInRequest containing the list of tasks.

    Returns:
        The newly created AttendanceSession.

    Raises:
        409 — Already checked in today.
        400 — No tasks provided.
    """
    existing = await get_today_session(db, employee_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already checked in today.",
        )
    if not body.tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one task is required to check in.",
        )

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
    await db.flush()  # Get session.id before creating tasks

    for task in body.tasks:
        db.add(TaskEntry(
            session_id=session.id,
            project_id=task.project_id,
            employee_id=employee_id,
            description=task.description,
            hours_logged=task.hours,
        ))

    await db.commit()
    db.expire(session)
    await db.refresh(session)
    return session


async def check_out(db: AsyncSession, employee_id) -> AttendanceSession:
    """
    Check out the employee and calculate total hours worked.

    Finds today's open session, sets check_out_at to now,
    and computes total_hours as decimal hours.

    Args:
        db:          Async database session.
        employee_id: UUID of the employee checking out.

    Returns:
        The updated AttendanceSession.

    Raises:
        404 — No session found (employee hasn't checked in).
        409 — Already checked out today.
    """
    session = await get_today_session(db, employee_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session found. Please check in first.",
        )
    if session.check_out_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already checked out today.",
        )

    now = datetime.now(timezone.utc)
    session.check_out_at = now

    # Ensure check_in_at is timezone-aware before subtraction
    check_in = session.check_in_at
    if check_in.tzinfo is None:
        check_in = check_in.replace(tzinfo=timezone.utc)

    # Total hours as decimal (e.g. 8.5 = 8 hours 30 minutes)
    session.total_hours = round((now - check_in).total_seconds() / 3600, 2)

    await db.commit()

    # Expire the session object so SQLAlchemy fully discards the in-memory
    # state (including the already-loaded tasks collection) before refresh.
    # Without this, the selectin relationship appends a second copy of every
    # task on top of the ones already in memory — causing duplicates.
    db.expire(session)
    await db.refresh(session)
    return session


async def get_sessions_for_month(
    db: AsyncSession, employee_id, month: int, year: int
) -> list:
    """
    Return all attendance sessions for an employee in a given month,
    each with their associated tasks and project names.

    Args:
        db:          Async database session.
        employee_id: UUID of the employee.
        month:       Calendar month (1-12).
        year:        Calendar year.

    Returns:
        List of dicts, each representing one session with its tasks.
        Ordered newest first.
    """
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
        # Load tasks with their project names in one query
        tasks_result = await db.execute(
            select(TaskEntry)
            .options(joinedload(TaskEntry.project))
            .where(TaskEntry.session_id == s.id)
            .order_by(TaskEntry.sort_order)
        )
        tasks = tasks_result.unique().scalars().all()
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
            # Comma-joined task descriptions for quick display in tables
            "tasks_summary": ", ".join(t["description"] for t in task_list),
        })
    return output


def generate_csv(sessions: list) -> str:
    """
    Convert a list of session dicts (from get_sessions_for_month) to a CSV string.

    Columns: Date, Reporting task, Check in time, Check out time, Total hours

    Args:
        sessions: List of session dicts as returned by get_sessions_for_month.

    Returns:
        CSV content as a string, ready to stream to the client.
    """
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
