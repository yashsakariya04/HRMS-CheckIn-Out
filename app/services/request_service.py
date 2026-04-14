# app/services/request_service.py
"""
app/services/request_service.py — Leave/WFH Request Business Logic
==================================================================
Handles the full lifecycle of employee requests: create, list,
approve, reject, and cancel.

Request types and their approval side-effects:
  leave        → deducts working days only (skips weekends + holidays — no sandwich policy)
                 uses comp_off balance first, then casual; casual can go negative
  wfh          → marks attendance session work_mode = 'wfh' for each day
  missing_time → fills in checkout time on the linked session
  comp_off     → credits +1 to comp_off balance (employee earned a day off)

Submission-time validation rules (enforced in create_request):
  1. Leave cannot be taken on a weekend (Saturday / Sunday).
  2. Leave cannot be taken on a company holiday.
  3. Leave cannot overlap an already-approved WFH request on the same dates.
  4. Comp-off date must be a weekend (Sat/Sun) or a company holiday.

Rejection has zero side-effects on any balance or session.
"""
from datetime import date, datetime, timezone, timedelta
from typing import List, Set
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.holiday import Holiday
from app.models.leave_wfh_request import LeaveWFHRequest
from app.schemas.request_Emp import RequestCreate, RequestListResponse, RequestResponse


# ─────────────────────────────────────────────────────────────
# DATE UTILITY HELPERS
# ─────────────────────────────────────────────────────────────

def _date_range(from_date: date, to_date: date) -> List[date]:
    """Return every calendar date from from_date to to_date inclusive."""
    days = []
    current = from_date
    while current <= to_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def _is_weekend(d: date) -> bool:
    """Return True if the date is Saturday (5) or Sunday (6)."""
    return d.weekday() >= 5


async def _get_holiday_dates(
    db: AsyncSession,
    organization_id,
    from_date: date,
    to_date: date,
) -> Set[date]:
    """
    Return the set of holiday dates for the organization that fall
    within [from_date, to_date].
    """
    result = await db.execute(
        select(Holiday.holiday_date).where(
            Holiday.organization_id == organization_id,
            Holiday.holiday_date >= from_date,
            Holiday.holiday_date <= to_date,
        )
    )
    return {row for row in result.scalars().all()}


def _working_days(all_dates: List[date], holiday_dates: Set[date]) -> List[date]:
    """
    Filter a list of dates down to actual working days only.
    Excludes weekends and company holidays (no sandwich policy).
    """
    return [d for d in all_dates if not _is_weekend(d) and d not in holiday_dates]


# ─────────────────────────────────────────────────────────────
# SUBMISSION VALIDATION RULES
# ─────────────────────────────────────────────────────────────

async def _validate_leave_request(
    db: AsyncSession,
    employee: Employee,
    body: RequestCreate,
) -> None:
    """
    Enforce all business rules for leave requests at submission time.

    Rules checked:
      1. No leave on weekends (Saturday / Sunday).
      2. No leave on a company holiday (it is already a day off).
      3. No leave on a date where an approved WFH request already exists.
    """
    all_dates = _date_range(body.from_date, body.to_date)

    # Rule 1 — no weekends
    weekend_dates = [d for d in all_dates if _is_weekend(d)]
    if weekend_dates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Leave cannot be taken on weekends. "
                f"Weekend dates in your range: "
                f"{', '.join(str(d) for d in weekend_dates)}."
            ),
        )

    # Rule 2 — no leave on a holiday
    holiday_dates = await _get_holiday_dates(
        db, employee.organization_id, body.from_date, body.to_date
    )
    if holiday_dates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Leave cannot be taken on a company holiday. "
                f"Holiday dates in your range: "
                f"{', '.join(str(d) for d in sorted(holiday_dates))}."
            ),
        )

    # Rule 3 — no leave where WFH is already approved
    wfh_result = await db.execute(
        select(LeaveWFHRequest).where(
            LeaveWFHRequest.employee_id == employee.id,
            LeaveWFHRequest.request_type == "wfh",
            LeaveWFHRequest.status == "approved",
            LeaveWFHRequest.from_date <= body.to_date,
            LeaveWFHRequest.to_date >= body.from_date,
        )
    )
    if wfh_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave cannot be taken on dates where a WFH request is already approved.",
        )


async def _validate_comp_off_request(
    db: AsyncSession,
    employee: Employee,
    body: RequestCreate,
) -> None:
    """
    Enforce business rules for comp-off requests at submission time.

    Rule: The date must be a weekend (Saturday/Sunday) or a company holiday.
    Comp-off is earned by working on a non-working day.
    """
    d = body.from_date  # comp_off is always a single day

    if _is_weekend(d):
        return  # weekend — valid

    holiday_dates = await _get_holiday_dates(
        db, employee.organization_id, d, d
    )
    if d in holiday_dates:
        return  # holiday — valid

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Comp-off can only be claimed for working on a weekend or a company holiday. "
            f"{d} is a regular working day."
        ),
    )


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
    Deduct the number of actual working days in the leave range.

    Working days = all dates in [from_date, to_date] that are NOT
    weekends and NOT company holidays (no sandwich policy).

    Priority chain for deduction:
      Priority 1 — comp_off balance > 0  → deduct from comp_off.
      Priority 2 — comp_off = 0          → deduct from casual (may go negative).
    """
    all_dates = _date_range(req.from_date, req.to_date)
    holiday_dates = await _get_holiday_dates(
        db, req.organization_id, req.from_date, req.to_date
    )
    days = len(_working_days(all_dates, holiday_dates))

    if days == 0:
        # Entire range is weekends/holidays — nothing to deduct.
        return

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

    Runs all submission-time validation rules before saving:
      - leave     : no weekends, no holidays, no overlap with approved WFH
      - comp_off  : date must be a weekend or company holiday
      - missing_time: links the attendance session for the date
    """
    # —— Submission-time rule enforcement ———————————————————————————
    if body.request_type == "leave":
        await _validate_leave_request(db, employee, body)

    elif body.request_type == "comp_off":
        await _validate_comp_off_request(db, employee, body)

    # —— missing_time: link the attendance session —————————————————————
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
        checkout_time=body.checkout_time if body.request_type == "missing_time" else None,
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
        IST_OFFSET = timedelta(hours=5, minutes=30)
        session.check_out_at = (
            datetime.combine(session.session_date, req.checkout_time) - IST_OFFSET
        ).replace(tzinfo=timezone.utc)
        session.is_corrected = True
        check_in = session.check_in_at
        if check_in.tzinfo is None:
            check_in = check_in.replace(tzinfo=timezone.utc)
        session.total_hours = round(
            (session.check_out_at - check_in).total_seconds() / 3600, 2
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