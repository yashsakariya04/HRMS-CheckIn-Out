# import csv
# import io
# from datetime import date
# from uuid import UUID

# from fastapi.responses import StreamingResponse
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.attendance_session import AttendanceSession
# from app.models.employee import Employee
# from app.models.task_entry import TaskEntry
# from app.schemas.reporting import AttendanceRow, EmployeeDropdownItem, ReportingResponse


# async def get_all_employees(db: AsyncSession) -> list[EmployeeDropdownItem]:
#     result = await db.execute(
#         select(Employee).where(Employee.is_active == True).order_by(Employee.full_name)
#     )
#     return [
#         EmployeeDropdownItem(id=str(e.id), full_name=e.full_name or "", designation=e.designation)
#         for e in result.scalars().all()
#     ]


# async def get_employee_report(
#     employee_id: UUID, whole_month: bool, db: AsyncSession
# ) -> ReportingResponse:
#     today = date.today()

#     month_result = await db.execute(
#         select(AttendanceSession).where(
#             AttendanceSession.employee_id == employee_id,
#             AttendanceSession.session_date >= today.replace(day=1),
#         )
#     )
#     month_sessions = month_result.scalars().all()
#     hours = [float(s.total_hours) for s in month_sessions if s.total_hours is not None]
#     avg_hours = round(sum(hours) / len(hours), 1) if hours else 0.0

#     stmt = select(AttendanceSession).where(AttendanceSession.employee_id == employee_id)
#     if not whole_month:
#         stmt = stmt.where(AttendanceSession.session_date >= today.replace(day=1))
#     stmt = stmt.order_by(AttendanceSession.session_date.desc())

#     sessions = (await db.execute(stmt)).scalars().all()

#     records = []
#     for session in sessions:
#         tasks = (await db.execute(
#             select(TaskEntry)
#             .where(TaskEntry.session_id == session.id)
#             .order_by(TaskEntry.sort_order)
#         )).scalars().all()

#         records.append(AttendanceRow(
#             date=session.session_date,
#             tasks=", ".join(t.description for t in tasks) if tasks else "—",
#             check_in_at=session.check_in_at,
#             check_out_at=session.check_out_at,
#         ))

#     return ReportingResponse(avg_hours_this_month=avg_hours, records=records)


# async def get_employee_report_csv(employee_id: UUID, db: AsyncSession) -> StreamingResponse:
#     employee = (await db.execute(select(Employee).where(Employee.id == employee_id))).scalars().first()
#     emp_name = (employee.full_name or str(employee_id)).replace(" ", "_") if employee else str(employee_id)

#     sessions = (await db.execute(
#         select(AttendanceSession)
#         .where(AttendanceSession.employee_id == employee_id)
#         .order_by(AttendanceSession.session_date.desc())
#     )).scalars().all()

#     output = io.StringIO()
#     writer = csv.writer(output)
#     writer.writerow(["Date", "Reporting Task", "Check In Time", "Check Out Time"])

#     for session in sessions:
#         tasks = (await db.execute(
#             select(TaskEntry)
#             .where(TaskEntry.session_id == session.id)
#             .order_by(TaskEntry.sort_order)
#         )).scalars().all()

#         writer.writerow([
#             session.session_date.strftime("%d-%m-%Y"),
#             ", ".join(t.description for t in tasks) if tasks else "—",
#             session.check_in_at.strftime("%I:%M %p") if session.check_in_at else "—",
#             session.check_out_at.strftime("%I:%M %p") if session.check_out_at else "—",
#         ])

#     output.seek(0)
#     filename = f"report_{emp_name}_{date.today().strftime('%b_%Y')}.csv"
#     return StreamingResponse(
#         iter([output.getvalue()]),
#         media_type="text/csv",
#         headers={"Content-Disposition": f"attachment; filename={filename}"},
#     )


import csv
import io
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee
from app.models.task_entry import TaskEntry
from app.schemas.reporting import AttendanceRow, EmployeeDropdownItem, ReportingResponse


async def get_all_employees(db: AsyncSession) -> list[EmployeeDropdownItem]:
    result = await db.execute(
        select(Employee).where(Employee.is_active == True).order_by(Employee.full_name)
    )
    employees = result.scalars().all()
    return [
        EmployeeDropdownItem(id=str(e.id), full_name=e.full_name or "", designation=e.designation)
        for e in employees
    ]


async def get_employee_report(
    employee_id: UUID, whole_month: bool, db: AsyncSession
) -> ReportingResponse:
    today = date.today()

    # Always compute avg from current month
    month_stmt = select(AttendanceSession).where(
        AttendanceSession.employee_id == employee_id,
        AttendanceSession.session_date >= today.replace(day=1),
    )
    month_result = await db.execute(month_stmt)
    month_sessions = month_result.scalars().all()
    hours = [float(s.total_hours) for s in month_sessions if s.total_hours is not None]
    avg_hours = round(sum(hours) / len(hours), 1) if hours else 0.0

    # Filter sessions based on toggle
    stmt = select(AttendanceSession).where(
        AttendanceSession.employee_id == employee_id
    )
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
        task_str = ", ".join(t.description for t in tasks) if tasks else "—"

        records.append(AttendanceRow(
            date=session.session_date,
            tasks=task_str,
            check_in_at=session.check_in_at,
            check_out_at=session.check_out_at,
        ))

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
        task_str = ", ".join(t.description for t in tasks) if tasks else "—"

        check_in = session.check_in_at.strftime("%I:%M %p") if session.check_in_at else "—"
        check_out = session.check_out_at.strftime("%I:%M %p") if session.check_out_at else "—"
        writer.writerow([session.session_date.strftime("%d-%m-%Y"), task_str, check_in, check_out])

    output.seek(0)
    month_label = date.today().strftime("%b_%Y")
    filename = f"report_{emp_name}_{month_label}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
