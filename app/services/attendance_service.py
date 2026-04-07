# app/services/attendance_service.py
"""
Attendance service — all check-in/check-out business logic.

Rules enforced here:
    - One session per employee per day
    - Cannot check out without an open session
    - At least one task required on check-in
    - total_hours computed on checkout
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.attendance_session import AttendanceSession
from app.models.task_entry import TaskEntry
from app.schemas.attendance import CheckInRequest


def get_today_session(
    db: Session,
    employee_id: str,
) -> Optional[AttendanceSession]:
    """
    Fetch today's attendance session for the employee.
    Returns None if employee has not checked in today.
    Used by GET /attendance/today to determine page state.
    """
    today = date.today()
    return db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == employee_id,
        AttendanceSession.session_date == today,
    ).first()


def check_in(
    db: Session,
    employee_id: str,
    organization_id: str,
    body: CheckInRequest,
) -> AttendanceSession:
    """
    Create a new attendance session with tasks.

    Steps:
        1. Verify no session exists today (one per day rule)
        2. Verify at least one task is provided
        3. Create attendance session with check_in_at = now
        4. Create task entries linked to the session
        5. Return session with tasks

    Raises:
        409 if employee already checked in today
        400 if no tasks provided
    """
    # RULE: One session per employee per day
    existing = get_today_session(db, employee_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already checked in today.",
        )

    # RULE: At least one task is required
    if not body.tasks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one task is required to check in.",
        )

    now = datetime.now(timezone.utc)

    # Create the attendance session
    session = AttendanceSession(
        employee_id=employee_id,
        organization_id=organization_id,
        session_date=date.today(),
        check_in_at=now,
        work_mode="office",
        is_corrected=False,
    )
    db.add(session)
    db.flush()  # flush to get session.id before creating tasks

    # Create task entries linked to this session
    for task in body.tasks:
        task_entry = TaskEntry(
            session_id=session.id,
            project_id=task.project_id,
            employee_id=employee_id,
            description=task.description,
            hours_logged=task.hours,
        )
        db.add(task_entry)

    db.commit()
    db.refresh(session)
    _ = session.tasks  # trigger eager load while session is open
    return session


def check_out(
    db: Session,
    employee_id: str,
) -> AttendanceSession:
    """
    Close today's open attendance session.

    Steps:
        1. Find today's open session (check_out_at IS NULL)
        2. Set check_out_at = now
        3. Compute total_hours = (check_out - check_in) in decimal hours
        4. Save and return updated session

    Raises:
        404 if no open session found for today
    """
    # Check if a session exists today
    session = db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == employee_id,
        AttendanceSession.session_date == date.today(),
    ).first()

    # RULE: Cannot check out without an open session
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

    # Compute total hours — guard against timezone-naive check_in_at from DB
    check_in = session.check_in_at
    if check_in.tzinfo is None:
        check_in = check_in.replace(tzinfo=timezone.utc)
    delta = now - check_in
    session.total_hours = round(delta.total_seconds() / 3600, 2)

    db.commit()
    db.refresh(session)
    _ = session.tasks  # trigger eager load while session is open
    return session

def get_sessions_for_month(
    db: Session,
    employee_id,
    month: int,
    year: int,
) -> list:
    """
    Fetch all sessions for a given month with tasks and project names.
    Tasks and project load automatically via joined relationships.
    Returns list of dicts ready for SessionListResponse.
    """
    from sqlalchemy import extract

    sessions = db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == employee_id,
        extract("month", AttendanceSession.session_date) == month,
        extract("year", AttendanceSession.session_date) == year,
    ).order_by(AttendanceSession.session_date.desc()).all()

    result = []
    for s in sessions:
        tasks = [
            {
                "id": t.id,
                "description": t.description,
                "hours_logged": float(t.hours_logged),
                "project_id": t.project_id,
                "project_name": t.project.name if t.project else "",
            }
            for t in s.tasks
        ]
        result.append({
            "id": s.id,
            "session_date": s.session_date,
            "check_in_at": s.check_in_at,
            "check_out_at": s.check_out_at,
            "total_hours": float(s.total_hours) if s.total_hours else None,
            "work_mode": s.work_mode,
            "is_corrected": s.is_corrected,
            "tasks": tasks,
            "tasks_summary": ", ".join(t["description"] for t in tasks),
        })
    return result


def generate_csv(sessions: list) -> str:
    """Build CSV string from session list for the Download button."""
    import io
    import csv

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Reporting task", "Check in time", "Check out time", "Total hours"])

    for s in sessions:
        date_str = s["session_date"].strftime("%d-%m-%Y")
        check_in = s["check_in_at"].strftime("%I:%M %p")
        check_out = s["check_out_at"].strftime("%I:%M %p") if s["check_out_at"] else "—"
        total = f"{s['total_hours']:.2f}" if s["total_hours"] is not None else "—"
        writer.writerow([date_str, s["tasks_summary"], check_in, check_out, total])

    return output.getvalue()
