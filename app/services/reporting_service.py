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
    result = await db.execute(
        select(Employee).where(Employee.is_active == True).order_by(Employee.full_name)
    )
    return [
        EmployeeDropdownItem(id=str(e.id), full_name=e.full_name or "", designation=e.designation)
        for e in result.scalars().all()
    ]


async def get_employee_report(
    employee_id: UUID, whole_month: bool, db: AsyncSession
) -> ReportingResponse:
    """
    Build the attendance report for a specific employee.

    Always computes avg_hours from the current month regardless of whole_month flag.
    The records list is filtered by whole_month:
      - False → current month only
      - True  → all sessions ever

    Args:
        employee_id: UUID of the employee.
        whole_month: If True, return all sessions; otherwise current month only.
        db:          Async database session.

    Returns:
        ReportingResponse with avg_hours_this_month and records list.
    """
    today = date.today()

    # Always compute average from current month
    month_result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.session_date >= today.replace(day=1),
        )
    )
    month_sessions = month_result.scalars().all()
    hours = [float(s.total_hours) for s in month_sessions if s.total_hours is not None]
    avg_hours = round(sum(hours) / len(hours), 1) if hours else 0.0

    # Filter sessions based on the whole_month toggle
    stmt = select(AttendanceSession).where(AttendanceSession.employee_id == employee_id)
    if not whole_month:
        stmt = stmt.where(AttendanceSession.session_date >= today.replace(day=1))
    stmt = stmt.order_by(AttendanceSession.session_date.desc())

    result = await db.execute(stmt)
    sessions = result.scalars().all()

    records = []
    for session in sessions:
        tasks_result = await db.execute(
            select(TaskEntry)
            .where(TaskEntry.session_id == session.id)
            .order_by(TaskEntry.sort_order)
        )
        tasks = tasks_result.scalars().all()

        records.append(AttendanceRow(
            date=session.session_date,
            tasks=_build_task_list(tasks),
            check_in_at=session.check_in_at,
            check_out_at=session.check_out_at,
        ))

    return ReportingResponse(avg_hours_this_month=avg_hours, records=records)


async def get_employee_report_csv(employee_id: UUID, db: AsyncSession) -> StreamingResponse:
    """
    Generate and stream a CSV attendance report for the given employee.

    Includes all sessions (no month filter). Filename format:
      report_<employee_name>_<Month_Year>.csv

    Args:
        employee_id: UUID of the employee.
        db:          Async database session.

    Returns:
        StreamingResponse with CSV content and appropriate headers.
    """
    emp_result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = emp_result.scalars().first()
    emp_name = (employee.full_name or str(employee_id)).replace(" ", "_") if employee else str(employee_id)

    result = await db.execute(
        select(AttendanceSession)
        .where(AttendanceSession.employee_id == employee_id)
        .order_by(AttendanceSession.session_date.desc())
    )
    sessions = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Reporting Task", "Check In Time", "Check Out Time"])

    for session in sessions:
        tasks_result = await db.execute(
            select(TaskEntry)
            .where(TaskEntry.session_id == session.id)
            .order_by(TaskEntry.sort_order)
        )
        tasks = tasks_result.scalars().all()
        task_str = _group_tasks_by_project(_build_task_list(tasks))

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
