# services/leave_request_service.py

from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.employee import Employee
from backend.app.models.leave_wfh_request import LeaveRequest

# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

LEAVES_PER_MONTH = 2          # adjust to your business rule
MAX_CARRY_FORWARD = 20        # unused leaves capped at 1


async def _get_employee_name(employee_id: UUID, db: AsyncSession) -> str:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalars().first()
    return emp.full_name if emp and emp.full_name else str(employee_id)


# ─────────────────────────────────────────────
# TAB 1 — REQUESTS
# ─────────────────────────────────────────────

async def get_all_requests(db: AsyncSession) -> list[dict]:
    """
    Return every leave / WFH request across all employees,
    newest first.  Used by the admin 'Requests' tab.
    """
    result = await db.execute(
        select(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    )
    requests = result.scalars().all()

    rows = []
    for req in requests:
        emp_name = await _get_employee_name(req.employee_id, db)
        rows.append({
            "id": req.id,
            "employee_name": emp_name,
            "request_type": req.request_type,
            "from_date": req.from_date,
            "to_date": req.to_date,
            "reason": req.reason,
            "status": req.status,
        })
    return rows


async def approve_request(request_id: UUID, admin_id: UUID, db: AsyncSession) -> dict:
    """
    Mark a pending request as approved.
    """
    result = await db.execute(
        select(LeaveRequest).where(LeaveRequest.id == request_id)
    )
    req = result.scalars().first()

    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if req.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve a request that is already '{req.status}'"
        )

    req.status = "approved"
    req.reviewed_by = admin_id
    req.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(req)

    return {"message": "Request approved successfully"}


async def reject_request(
    request_id: UUID,
    admin_id: UUID,
    rejection_note: str | None,
    db: AsyncSession,
) -> dict:
    """
    Mark a pending request as rejected, optionally with a note.
    """
    result = await db.execute(
        select(LeaveRequest).where(LeaveRequest.id == request_id)
    )
    req = result.scalars().first()

    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if req.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject a request that is already '{req.status}'"
        )

    req.status = "rejected"
    req.reviewed_by = admin_id
    req.reviewed_at = datetime.now(timezone.utc)
    req.rejection_note = rejection_note

    await db.commit()
    await db.refresh(req)

    return {"message": "Request rejected successfully"}

# ─────────────────────────────────────────────
# TAB 2 — LEAVE SUMMARY
# ─────────────────────────────────────────────

async def get_leave_summary(db: AsyncSession) -> list[dict]:
    """
    For every employee, compute:
      - leaves taken THIS calendar month (approved only)
      - leaves taken in PREVIOUS months  (approved only, grouped by month name)
      - leaves balance  = accumulated carry-forward minus this month's usage
    """
    today = date.today()
    current_month = today.month
    current_year = today.year

    # Fetch all approved leave (not WFH) requests
    result = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.request_type == "leave",
            LeaveRequest.status == "approved",
        )
    )
    all_leaves = result.scalars().all()

    # Group by employee
    by_employee: dict[UUID, list[LeaveRequest]] = defaultdict(list)
    for lv in all_leaves:
        by_employee[lv.employee_id].append(lv)

    rows = []
    for emp_id, leaves in by_employee.items():
        emp_name = await _get_employee_name(emp_id, db)

        this_month_count = 0
        prev_months: dict[str, int] = defaultdict(int)

        for lv in leaves:
            # Count days in range (inclusive)
            days = (lv.to_date - lv.from_date).days + 1
            month_key = lv.from_date.strftime("%b")   # e.g. "Feb"
            year = lv.from_date.year
            month = lv.from_date.month

            if year == current_year and month == current_month:
                this_month_count += days
            else:
                prev_months[month_key] += days

        # ── Balance logic ──────────────────────────────────────────────
        # Each past month gives LEAVES_PER_MONTH credits, capped at
        # MAX_CARRY_FORWARD unused leaves carried into the current month.
        # Simple approach: total earned so far this year minus total used.
        months_elapsed = current_month - 1          # Jan=0 months elapsed before current
        total_earned = months_elapsed * LEAVES_PER_MONTH
        total_used_prev = sum(prev_months.values())
        carry_forward = min(total_earned - total_used_prev, MAX_CARRY_FORWARD)
        balance = max(carry_forward + LEAVES_PER_MONTH - this_month_count, 0)

        rows.append({
            "employee_name": emp_name,
            "this_month_leaves": this_month_count,
            "previous_months": dict(prev_months),
            "leaves_balance": balance,
        })

    return rows