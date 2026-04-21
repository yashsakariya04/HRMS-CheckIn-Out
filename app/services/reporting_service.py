"""
app/services/reporting_service.py — Admin Reporting Business Logic
==================================================================
Generates attendance reports for individual employees.

Non-technical summary:
----------------------
Admins can view a detailed attendance report for any employee:
  - Average daily hours worked this month
  - Day-by-day attendance records with tasks and check-in/out times
  - Downloadable CSV version of the same data

The `whole_month` flag controls whether to show only the current
month or all historical records.
"""

import csv
import io
from datetime import date
from uuid import UUID

from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from collections import defaultdict

from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee
from app.models.task_entry import TaskEntry
from app.schemas.attendance import TaskInSession
from app.schemas.reporting import AttendanceRow, EmployeeDropdownItem, ReportingResponse


def _build_task_list(tasks: list) -> list:
    """Convert TaskEntry ORM objects to TaskInSession schema objects."""
    return [
        TaskInSession(
            id=t.id,
            description=t.description,
            hours_logged=float(t.hours_logged),
            project_id=t.project_id,
            project_name=t.project.name if t.project else "",
        )
        for t in tasks
    ]


def _group_tasks_by_project(tasks: list) -> str:
    """Group TaskInSession objects into 'ProjectA: task1, task2 | ProjectB: task3' format for CSV."""
    if not tasks:
        return "—"
    grouped = defaultdict(list)
    for t in tasks:
        grouped[t.project_name or "No Project"].append(t.description)
    return " | ".join(f"{proj}: {', '.join(descs)}" for proj, descs in grouped.items())


async def get_all_employees(db: AsyncSession) -> list[EmployeeDropdownItem]:
    """
    Return all active employees for the admin's employee selector dropdown.

    Args:
        db: Async database session.

    Returns:
        List of EmployeeDropdownItem sorted alphabetically by name.
    """
    result = await db.execute(select(Employee).where(Employee.is_active == True,Employee.role != "superadmin")
    .order_by(Employee.full_name)
    )
    return [
        EmployeeDropdownItem(id=str(e.id), full_name=e.full_name or "", designation=e.designation)
        for e in result.scalars().all()
    ]


async def get_employee_report(
    employee_id: UUID, whole_month: bool, db: AsyncSession
) -> ReportingResponse:
    today = date.today()

    month_result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.session_date >= today.replace(day=1),
        )
    )
    month_sessions = month_result.scalars().all()
    hours = [float(s.total_hours) for s in month_sessions if s.total_hours is not None]
    avg_hours = round(sum(hours) / len(hours), 1) if hours else 0.0

    stmt = select(AttendanceSession).where(AttendanceSession.employee_id == employee_id)
    if not whole_month:
        stmt = stmt.where(AttendanceSession.session_date >= today.replace(day=1))
    stmt = stmt.order_by(AttendanceSession.session_date.desc())

    result = await db.execute(stmt)
    sessions = result.scalars().all()

    if not sessions:
        return ReportingResponse(avg_hours_this_month=avg_hours, records=[])

    # Load all tasks for all sessions in one query — no N+1
    session_ids = [s.id for s in sessions]
    tasks_result = await db.execute(
        select(TaskEntry)
        .options(joinedload(TaskEntry.project))
        .where(TaskEntry.session_id.in_(session_ids))
        .order_by(TaskEntry.sort_order)
    )
    all_tasks = tasks_result.unique().scalars().all()

    tasks_by_session: dict = {}
    for t in all_tasks:
        tasks_by_session.setdefault(t.session_id, []).append(t)

    records = [
        AttendanceRow(
            date=s.session_date,
            tasks=_build_task_list(tasks_by_session.get(s.id, [])),
            check_in_at=s.check_in_at,
            check_out_at=s.check_out_at,
        )
        for s in sessions
    ]
    return ReportingResponse(avg_hours_this_month=avg_hours, records=records)


async def get_employee_report_csv(employee_id: UUID, db: AsyncSession) -> StreamingResponse:
    emp_result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = emp_result.scalars().first()
    emp_name = (employee.full_name or str(employee_id)).replace(" ", "_") if employee else str(employee_id)

    result = await db.execute(
        select(AttendanceSession)
        .where(AttendanceSession.employee_id == employee_id)
        .order_by(AttendanceSession.session_date.desc())
    )
    sessions = result.scalars().all()

    # Load all tasks in one query — no N+1
    session_ids = [s.id for s in sessions]
    tasks_result = await db.execute(
        select(TaskEntry)
        .options(joinedload(TaskEntry.project))
        .where(TaskEntry.session_id.in_(session_ids))
        .order_by(TaskEntry.sort_order)
    )
    all_tasks = tasks_result.unique().scalars().all()
    tasks_by_session: dict = {}
    for t in all_tasks:
        tasks_by_session.setdefault(t.session_id, []).append(t)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Reporting Task", "Check In Time", "Check Out Time"])

    for session in sessions:
        task_str = _group_tasks_by_project(_build_task_list(tasks_by_session.get(session.id, [])))
        writer.writerow([
            session.session_date.strftime("%d-%m-%Y"),
            task_str,
            session.check_in_at.strftime("%I:%M %p") if session.check_in_at else "—",
            session.check_out_at.strftime("%I:%M %p") if session.check_out_at else "—",
        ])

    output.seek(0)
    filename = f"report_{emp_name}_{date.today().strftime('%b_%Y')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
