# from datetime import date, datetime, timezone, timedelta
# from typing import List
# from uuid import UUID

# from fastapi import HTTPException, status
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.models.attendance_session import AttendanceSession
# from app.models.employee import Employee
# from app.models.employee_leave_balance import EmployeeLeaveBalance
# from app.models.leave_wfh_request import LeaveWFHRequest
# from app.schemas.request_Emp import RequestCreate, RequestListResponse, RequestResponse


# def _to_response(req: LeaveWFHRequest) -> RequestResponse:
#     return RequestResponse.model_validate(req)


# def _to_list_response(req: LeaveWFHRequest, employee: Employee) -> RequestListResponse:
#     return RequestListResponse(
#         id=req.id,
#         request_type=req.request_type,
#         from_date=req.from_date,
#         to_date=req.to_date,
#         reason=req.reason,
#         status=req.status,
#         linked_session_id=req.linked_session_id,
#         rejection_note=req.rejection_note,
#         reviewed_at=req.reviewed_at,
#         created_at=req.created_at,
#         employee_id=employee.id,
#         employee_name=employee.full_name,
#         employee_email=employee.email,
#     )


# async def _get_or_404(db: AsyncSession, request_id) -> LeaveWFHRequest:
#     result = await db.execute(select(LeaveWFHRequest).where(LeaveWFHRequest.id == request_id))
#     req = result.scalars().first()
#     if not req:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
#     return req


# async def _get_leave_balance(db: AsyncSession, employee_id, leave_type: str, target_date: date) -> EmployeeLeaveBalance:
#     result = await db.execute(
#         select(EmployeeLeaveBalance).where(
#             EmployeeLeaveBalance.employee_id == employee_id,
#             EmployeeLeaveBalance.leave_type == leave_type,
#             EmployeeLeaveBalance.year == target_date.year,
#             EmployeeLeaveBalance.month == target_date.month,
#         )
#     )
#     row = result.scalars().first()
#     if not row:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"No {leave_type} balance record found for this month.",
#         )
#     return row


# async def create_request(db: AsyncSession, employee: Employee, body: RequestCreate) -> RequestResponse:
#     linked_session_id = None

#     if body.request_type == "missing_time":
#         result = await db.execute(
#             select(AttendanceSession).where(
#                 AttendanceSession.employee_id == employee.id,
#                 AttendanceSession.session_date == body.from_date,
#             )
#         )
#         session = result.scalars().first()
#         if not session:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=f"No attendance session found for {body.from_date}.",
#             )
#         linked_session_id = session.id

#     req = LeaveWFHRequest(
#         employee_id=employee.id,
#         organization_id=employee.organization_id,
#         request_type=body.request_type,
#         from_date=body.from_date,
#         to_date=body.to_date,
#         reason=body.reason,
#         linked_session_id=linked_session_id,
#         status="pending",
#     )
#     db.add(req)
#     await db.commit()
#     await db.refresh(req)
#     return _to_response(req)


# async def get_user_requests(db: AsyncSession, employee: Employee) -> List[RequestResponse]:
#     result = await db.execute(
#         select(LeaveWFHRequest).where(
#             LeaveWFHRequest.employee_id == employee.id
#         ).order_by(LeaveWFHRequest.created_at.desc())
#     )
#     return [_to_response(r) for r in result.scalars().all()]


# async def get_all_requests(db: AsyncSession) -> List[RequestListResponse]:
#     result = await db.execute(
#         select(LeaveWFHRequest, Employee)
#         .join(Employee, Employee.id == LeaveWFHRequest.employee_id)
#         .order_by(LeaveWFHRequest.created_at.desc())
#     )
#     return [_to_list_response(req, emp) for req, emp in result.all()]


# async def approve_request(db: AsyncSession, request_id, admin: Employee) -> RequestResponse:
#     req = await _get_or_404(db, request_id)

#     if req.status != "pending":
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is already {req.status}.")

#     if req.request_type == "leave":
#         days = (req.to_date - req.from_date).days + 1
#         balance = await _get_leave_balance(db, req.employee_id, "casual", req.from_date)
#         if float(balance.closing_balance or 0) < days:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=f"Insufficient leave balance. Available: {balance.closing_balance}, Required: {days}.",
#             )
#         balance.used = float(balance.used) + days
#         balance.closing_balance = (
#             float(balance.opening_balance) + float(balance.accrued)
#             - float(balance.used) + float(balance.adjusted)
#         )

#     elif req.request_type == "wfh":
#         current = req.from_date
#         while current <= req.to_date:
#             result = await db.execute(
#                 select(AttendanceSession).where(
#                     AttendanceSession.employee_id == req.employee_id,
#                     AttendanceSession.session_date == current,
#                 )
#             )
#             session = result.scalars().first()
#             if session:
#                 session.work_mode = "wfh"
#             current += timedelta(days=1)

#     elif req.request_type == "missing_time":
#         if not req.linked_session_id:
#             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No linked session found on this request.")
#         result = await db.execute(
#             select(AttendanceSession).where(AttendanceSession.id == req.linked_session_id)
#         )
#         session = result.scalars().first()
#         if not session:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked attendance session no longer exists.")
#         checkout_time = datetime(
#             session.session_date.year, session.session_date.month, session.session_date.day,
#             18, 30, 0, tzinfo=timezone.utc,
#         )
#         session.check_out_at = checkout_time
#         session.is_corrected = True
#         check_in = session.check_in_at
#         if check_in.tzinfo is None:
#             check_in = check_in.replace(tzinfo=timezone.utc)
#         session.total_hours = round((checkout_time - check_in).total_seconds() / 3600, 2)

#     elif req.request_type == "comp_off":
#         balance = await _get_leave_balance(db, req.employee_id, "comp_off", req.from_date)
#         balance.accrued = float(balance.accrued) + 1
#         balance.closing_balance = (
#             float(balance.opening_balance) + float(balance.accrued)
#             - float(balance.used) + float(balance.adjusted)
#         )

#     req.status = "approved"
#     req.reviewed_by = admin.id
#     req.reviewed_at = datetime.now(timezone.utc)

#     await db.commit()
#     await db.refresh(req)
#     return _to_response(req)


# async def reject_request(db: AsyncSession, request_id, admin: Employee, note: str | None) -> RequestResponse:
#     req = await _get_or_404(db, request_id)

#     if req.status != "pending":
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is already {req.status}.")

#     req.status = "rejected"
#     req.reviewed_by = admin.id
#     req.reviewed_at = datetime.now(timezone.utc)
#     req.rejection_note = note

#     await db.commit()
#     await db.refresh(req)
#     return _to_response(req)


# async def cancel_request(db: AsyncSession, request_id, employee: Employee) -> None:
#     req = await _get_or_404(db, request_id)

#     if req.employee_id != employee.id:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only cancel your own requests.")
#     if req.status != "pending":
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot cancel a request that is already {req.status}.")

#     await db.delete(req)
#     await db.commit()


# app/services/request_service.py
"""
app/services/request_service.py — Leave/WFH Request Business Logic
==================================================================
Handles the full lifecycle of employee requests: create, list,
approve, reject, and cancel.

Request types and their approval side-effects:
  leave        → deducts 1 day from leave balance (comp_off first, then casual;
                 casual can go negative — debt is offset by future accruals)
  wfh          → marks attendance session work_mode = 'wfh' for each day
  missing_time → fills in checkout time on the linked session (18:30 UTC)
  comp_off     → credits +1 to comp_off balance (employee earned a day off)

Rejection has zero side-effects on any balance or session.
"""
from datetime import date, datetime, timezone, timedelta
from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest
from app.schemas.request_Emp import RequestCreate, RequestListResponse, RequestResponse


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _to_response(req: LeaveWFHRequest) -> RequestResponse:
    """Convert a LeaveWFHRequest ORM object to a RequestResponse schema."""
    return RequestResponse.model_validate(req)


def _to_list_response(req: LeaveWFHRequest, employee: Employee) -> RequestListResponse:
    """Convert a (LeaveWFHRequest, Employee) join row to a RequestListResponse schema."""
    return RequestListResponse(
        id=req.id,
        request_type=req.request_type,
        from_date=req.from_date,
        to_date=req.to_date,
        reason=req.reason,
        status=req.status,
        linked_session_id=req.linked_session_id,
        rejection_note=req.rejection_note,
        reviewed_at=req.reviewed_at,
        created_at=req.created_at,
        employee_id=employee.id,
        employee_name=employee.full_name,
        employee_email=employee.email,
    )


async def _get_or_404(db: AsyncSession, request_id) -> LeaveWFHRequest:
    """Fetch a request by ID or raise HTTP 404 if not found."""
    result = await db.execute(
        select(LeaveWFHRequest).where(LeaveWFHRequest.id == request_id)
    )
    req = result.scalars().first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found.",
        )
    return req


async def _get_balance_or_none(
    db: AsyncSession,
    employee_id,
    leave_type: str,
    target_date: date,
) -> EmployeeLeaveBalance | None:
    """
    Fetch the leave balance row for (employee, leave_type, year, month).
    Returns None if the row does not exist — callers decide how to handle that.
    """
    result = await db.execute(
        select(EmployeeLeaveBalance).where(
            EmployeeLeaveBalance.employee_id == employee_id,
            EmployeeLeaveBalance.leave_type == leave_type,
            EmployeeLeaveBalance.year == target_date.year,
            EmployeeLeaveBalance.month == target_date.month,
        )
    )
    return result.scalars().first()


def _recalc_closing(row: EmployeeLeaveBalance) -> None:
    """
    Recompute closing_balance in-place after any change to used / accrued / adjusted.
    Formula: closing = opening + accrued − used + adjusted
    Closing CAN be negative (debt scenario for casual leave).
    """
    row.closing_balance = (
        float(row.opening_balance)
        + float(row.accrued)
        - float(row.used)
        + float(row.adjusted)
    )


# ─────────────────────────────────────────────────────────────
# LEAVE APPROVAL — PRIORITY CHAIN
# ─────────────────────────────────────────────────────────────

async def _approve_leave(
    db: AsyncSession,
    req: LeaveWFHRequest,
) -> None:
    """
    Deduct 1 day of leave using this priority:

    Priority 1 — comp_off balance > 0
        → deduct 1 from comp_off, casual untouched.

    Priority 2 — comp_off = 0, casual balance > 0
        → deduct 1 from casual.

    Priority 3 — both = 0 (or no row exists yet)
        → deduct 1 from casual anyway → balance goes negative (debt).
          Future monthly accruals will offset the debt before adding
          spendable leave (+1 each month offsets -1 before it becomes
          spendable — handled by the rollover job).

    NOTE: This function always deducts exactly 1 day regardless of the
    date range on the request, because your rule is 1 leave = 1 calendar
    event, not 1 leave per day in the range.  If you later want multi-day
    deductions change `days = 1` to `days = (req.to_date - req.from_date).days + 1`
    and apply the same priority chain per-day or as a lump sum.
    """
    days = 1  # 1 leave token consumed per approval regardless of date range

    comp_off_row = await _get_balance_or_none(
        db, req.employee_id, "comp_off", req.from_date
    )
    if comp_off_row is None:
        # Rollover may not have run yet for this month — look back at the
        # most recent comp_off row across any month.
        result = await db.execute(
            select(EmployeeLeaveBalance)
            .where(
                EmployeeLeaveBalance.employee_id == req.employee_id,
                EmployeeLeaveBalance.leave_type == "comp_off",
            )
            .order_by(
                EmployeeLeaveBalance.year.desc(),
                EmployeeLeaveBalance.month.desc(),
            )
            .limit(1)
        )
        comp_off_row = result.scalars().first()
    comp_off_balance = float(comp_off_row.closing_balance or 0) if comp_off_row else 0.0

    if comp_off_balance > 0:
        # ── Priority 1: spend comp_off ──────────────────────────────
        comp_off_row.used = float(comp_off_row.used) + days
        _recalc_closing(comp_off_row)
        # casual balance is NOT touched

    else:
        # ── Priority 2 & 3: spend casual (allow negative) ──────────
        casual_row = await _get_balance_or_none(
            db, req.employee_id, "casual", req.from_date
        )

        if casual_row is None:
            # No balance row for this month yet (rollover job hasn't run).
            # Create one on the fly with opening = 0, so the debt is visible.
            casual_row = EmployeeLeaveBalance(
                employee_id=req.employee_id,
                leave_type="casual",
                year=req.from_date.year,
                month=req.from_date.month,
                opening_balance=0,
                accrued=0,
                used=0,
                adjusted=0,
                closing_balance=0,
            )
            db.add(casual_row)
            await db.flush()  # get the PK before mutating

        casual_row.used = float(casual_row.used) + days
        _recalc_closing(casual_row)
        # closing_balance may now be negative — that is intentional


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────

async def create_request(
    db: AsyncSession,
    employee: Employee,
    body: RequestCreate,
) -> RequestResponse:
    """
    Create a new pending request for the employee.

    For missing_time requests, automatically links the attendance session
    for the specified date. Raises 400 if no session exists on that date.
    """
    linked_session_id = None

    if body.request_type == "missing_time":
        result = await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.employee_id == employee.id,
                AttendanceSession.session_date == body.from_date,
            )
        )
        session = result.scalars().first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No attendance session found for {body.from_date}.",
            )
        linked_session_id = session.id

    req = LeaveWFHRequest(
        employee_id=employee.id,
        organization_id=employee.organization_id,
        request_type=body.request_type,
        from_date=body.from_date,
        to_date=body.to_date,
        reason=body.reason,
        linked_session_id=linked_session_id,
        status="pending",
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return _to_response(req)


async def get_user_requests(
    db: AsyncSession,
    employee: Employee,
) -> List[RequestResponse]:
    """Return all requests submitted by the given employee, newest first."""
    result = await db.execute(
        select(LeaveWFHRequest)
        .where(LeaveWFHRequest.employee_id == employee.id)
        .order_by(LeaveWFHRequest.created_at.desc())
    )
    return [_to_response(r) for r in result.scalars().all()]


async def get_all_requests(db: AsyncSession) -> List[RequestListResponse]:
    """Return all requests across all employees with employee details, newest first."""
    result = await db.execute(
        select(LeaveWFHRequest, Employee)
        .join(Employee, Employee.id == LeaveWFHRequest.employee_id)
        .order_by(LeaveWFHRequest.created_at.desc())
    )
    return [_to_list_response(req, emp) for req, emp in result.all()]


async def approve_request(
    db: AsyncSession,
    request_id,
    admin: Employee,
) -> RequestResponse:
    """
    Approve a pending request and apply its side-effects.

    Raises 400 if the request is not in 'pending' status.
    See module docstring for per-type side-effects.
    """
    req = await _get_or_404(db, request_id)

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {req.status}.",
        )

    # ── Per-type side effects ────────────────────────────────────────

    if req.request_type == "leave":
        # Priority chain: comp_off first → casual → allow negative
        await _approve_leave(db, req)

    elif req.request_type == "wfh":
        # No balance check — unlimited. Just mark sessions.
        current = req.from_date
        while current <= req.to_date:
            result = await db.execute(
                select(AttendanceSession).where(
                    AttendanceSession.employee_id == req.employee_id,
                    AttendanceSession.session_date == current,
                )
            )
            session = result.scalars().first()
            if session:
                session.work_mode = "wfh"
            current += timedelta(days=1)

    elif req.request_type == "missing_time":
        # No balance check — unlimited. Correct the linked session.
        if not req.linked_session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No linked session found on this request.",
            )
        result = await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.id == req.linked_session_id
            )
        )
        session = result.scalars().first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked attendance session no longer exists.",
            )
        checkout_time = datetime(
            session.session_date.year,
            session.session_date.month,
            session.session_date.day,
            18, 30, 0,
            tzinfo=timezone.utc,
        )
        session.check_out_at = checkout_time
        session.is_corrected = True
        check_in = session.check_in_at
        if check_in.tzinfo is None:
            check_in = check_in.replace(tzinfo=timezone.utc)
        session.total_hours = round(
            (checkout_time - check_in).total_seconds() / 3600, 2
        )

    elif req.request_type == "comp_off":
        # No balance check — unlimited submissions.
        # Approval credits +1 to comp_off balance (earn, not spend).
        comp_off_row = await _get_balance_or_none(
            db, req.employee_id, "comp_off", req.from_date
        )
        if comp_off_row is None:
            comp_off_row = EmployeeLeaveBalance(
                employee_id=req.employee_id,
                leave_type="comp_off",
                year=req.from_date.year,
                month=req.from_date.month,
                opening_balance=0,
                accrued=0,
                used=0,
                adjusted=0,
                closing_balance=0,
            )
            db.add(comp_off_row)
            await db.flush()

        comp_off_row.accrued = float(comp_off_row.accrued) + 1
        _recalc_closing(comp_off_row)

    # ── Stamp the request ────────────────────────────────────────────
    req.status = "approved"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(req)
    return _to_response(req)


async def reject_request(
    db: AsyncSession,
    request_id,
    admin: Employee,
    note: str | None,
) -> RequestResponse:
    """
    Reject a pending request with an optional note.
    No balance or session changes are made.
    Raises 400 if the request is not in 'pending' status.
    """
    req = await _get_or_404(db, request_id)

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {req.status}.",
        )

    # Rejection has zero side effects on any balance or session.
    req.status = "rejected"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.rejection_note = note

    await db.commit()
    await db.refresh(req)
    return _to_response(req)


async def cancel_request(
    db: AsyncSession,
    request_id,
    employee: Employee,
) -> None:
    """
    Employee cancels their own pending request (hard delete).
    Raises 403 if the request belongs to a different employee.
    Raises 400 if the request is no longer pending.
    """
    req = await _get_or_404(db, request_id)

    if req.employee_id != employee.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own requests.",
        )
    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a request that is already {req.status}.",
        )

    await db.delete(req)
    await db.commit()