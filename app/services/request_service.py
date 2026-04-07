# app/services/request_service.py
"""
Request service — all business logic for leave/wfh/missing_time/comp_off requests.

Approval side-effects:
    leave        → employee_leave_balance.used += days requested
    wfh          → attendance_session.work_mode = 'wfh' for each day in range
    missing_time → linked session: check_out_at = 18:30, is_corrected = True
    comp_off     → employee_leave_balance.accrued += 1 (comp_off type)
"""

from datetime import date, datetime, timezone, timedelta
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.leave_wfh_request import LeaveWFHRequest
from app.schemas.request_Emp import RequestCreate, RequestListResponse, RequestResponse


# ─── Helpers ───────────────────────────────────────────────────────────────

def _get_or_404(db: Session, request_id) -> LeaveWFHRequest:
    """Fetch a request by id or raise 404."""
    req = db.query(LeaveWFHRequest).filter(LeaveWFHRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    return req


def _get_leave_balance(
    db: Session, employee_id, leave_type: str, target_date: date
) -> EmployeeLeaveBalance:
    """
    Fetch the leave balance row for the given employee, type, and month.
    Raises 400 if no balance record exists (means leave was never set up).
    """
    row = db.query(EmployeeLeaveBalance).filter(
        EmployeeLeaveBalance.employee_id == employee_id,
        EmployeeLeaveBalance.leave_type == leave_type,
        EmployeeLeaveBalance.year == target_date.year,
        EmployeeLeaveBalance.month == target_date.month,
    ).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No {leave_type} balance record found for this month.",
        )
    return row


def _to_response(req: LeaveWFHRequest) -> RequestResponse:
    return RequestResponse.model_validate(req)


def _to_list_response(req: LeaveWFHRequest, employee: Employee) -> RequestListResponse:
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


# ─── Service functions ─────────────────────────────────────────────────────

def create_request(
    db: Session,
    employee: Employee,
    body: RequestCreate,
) -> RequestResponse:
    """
    Create a new request for the logged-in employee.

    Special handling:
        missing_time → must find an attendance session for that date,
                       stores linked_session_id
        comp_off     → single day only (validated in schema)
    """
    linked_session_id = None

    if body.request_type == "missing_time":
        session = db.query(AttendanceSession).filter(
            AttendanceSession.employee_id == employee.id,
            AttendanceSession.session_date == body.from_date,
        ).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No attendance session found for {body.from_date}. "
                       "You must have checked in on that day to submit a missing time request.",
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
    db.commit()
    db.refresh(req)
    return _to_response(req)


def get_user_requests(db: Session, employee: Employee) -> List[RequestResponse]:
    """Return all requests submitted by the logged-in employee, newest first."""
    rows = db.query(LeaveWFHRequest).filter(
        LeaveWFHRequest.employee_id == employee.id,
    ).order_by(LeaveWFHRequest.created_at.desc()).all()
    return [_to_response(r) for r in rows]


def get_all_requests(db: Session) -> List[RequestListResponse]:
    """
    Admin — return all requests across the org with employee name and email.
    Ordered newest first.
    """
    rows = (
        db.query(LeaveWFHRequest, Employee)
        .join(Employee, Employee.id == LeaveWFHRequest.employee_id)
        .order_by(LeaveWFHRequest.created_at.desc())
        .all()
    )
    return [_to_list_response(req, emp) for req, emp in rows]


def approve_request(db: Session, request_id, admin: Employee) -> RequestResponse:
    """
    Approve a pending request and apply the correct side-effect.

    Side-effects by type:
        leave        → deduct days from casual leave balance
        wfh          → set work_mode='wfh' on sessions in date range
        missing_time → set check_out_at=18:30, is_corrected=True on linked session
        comp_off     → add 1 day to comp_off balance
    """
    req = _get_or_404(db, request_id)

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {req.status}.",
        )

    # ── Side-effects ──────────────────────────────────────────────────────

    if req.request_type == "leave":
        days = (req.to_date - req.from_date).days + 1
        balance = _get_leave_balance(db, req.employee_id, "casual", req.from_date)
        if float(balance.closing_balance or 0) < days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient leave balance. Available: {balance.closing_balance}, Required: {days}.",
            )
        balance.used = float(balance.used) + days
        balance.closing_balance = (
            float(balance.opening_balance)
            + float(balance.accrued)
            - float(balance.used)
            + float(balance.adjusted)
        )

    elif req.request_type == "wfh":
        # Mark every session in the date range as wfh
        current = req.from_date
        while current <= req.to_date:
            session = db.query(AttendanceSession).filter(
                AttendanceSession.employee_id == req.employee_id,
                AttendanceSession.session_date == current,
            ).first()
            if session:
                session.work_mode = "wfh"
            current += timedelta(days=1)

    elif req.request_type == "missing_time":
        if not req.linked_session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No linked session found on this request.",
            )
        session = db.query(AttendanceSession).filter(
            AttendanceSession.id == req.linked_session_id,
        ).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked attendance session no longer exists.",
            )
        # Set checkout to 18:30 UTC on the session date
        checkout_time = datetime(
            session.session_date.year,
            session.session_date.month,
            session.session_date.day,
            18, 30, 0,
            tzinfo=timezone.utc,
        )
        session.check_out_at = checkout_time
        session.is_corrected = True
        # Recompute total_hours
        check_in = session.check_in_at
        if check_in.tzinfo is None:
            check_in = check_in.replace(tzinfo=timezone.utc)
        session.total_hours = round((checkout_time - check_in).total_seconds() / 3600, 2)

    elif req.request_type == "comp_off":
        balance = _get_leave_balance(db, req.employee_id, "comp_off", req.from_date)
        balance.accrued = float(balance.accrued) + 1
        balance.closing_balance = (
            float(balance.opening_balance)
            + float(balance.accrued)
            - float(balance.used)
            + float(balance.adjusted)
        )

    # ── Mark approved ─────────────────────────────────────────────────────
    req.status = "approved"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(req)
    return _to_response(req)


def reject_request(
    db: Session,
    request_id,
    admin: Employee,
    note: str | None,
) -> RequestResponse:
    """
    Reject a pending request. Optionally store a rejection note.
    No side-effects — nothing was applied yet.
    """
    req = _get_or_404(db, request_id)

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {req.status}.",
        )

    req.status = "rejected"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.rejection_note = note

    db.commit()
    db.refresh(req)
    return _to_response(req)


def cancel_request(db: Session, request_id, employee: Employee) -> None:
    """
    Employee cancels their own pending request.
    Raises 403 if not the owner, 400 if already processed.
    """
    req = _get_or_404(db, request_id)

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

    db.delete(req)
    db.commit()
