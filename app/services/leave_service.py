from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.leave_wfh_request import LeaveWFHRequest

LEAVES_PER_MONTH = 2
MAX_CARRY_FORWARD = 1


async def _get_employee_name(employee_id: UUID, db: AsyncSession) -> str:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalars().first()
    return emp.full_name if emp and emp.full_name else str(employee_id)


async def get_all_requests(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(LeaveWFHRequest).order_by(LeaveWFHRequest.created_at.desc())
    )
    rows = []
    for req in result.scalars().all():
        rows.append({
            "id": req.id,
            "employee_name": await _get_employee_name(req.employee_id, db),
            "request_type": req.request_type,
            "from_date": req.from_date,
            "to_date": req.to_date,
            "reason": req.reason,
            "status": req.status,
        })
    return rows


async def approve_request(request_id: UUID, admin_id: UUID, db: AsyncSession) -> dict:
    result = await db.execute(select(LeaveWFHRequest).where(LeaveWFHRequest.id == request_id))
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot approve a request that is already '{req.status}'")
    req.status = "approved"
    req.reviewed_by = admin_id
    req.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Request approved successfully"}


async def reject_request(request_id: UUID, admin_id: UUID, rejection_note: str | None, db: AsyncSession) -> dict:
    result = await db.execute(select(LeaveWFHRequest).where(LeaveWFHRequest.id == request_id))
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot reject a request that is already '{req.status}'")
    req.status = "rejected"
    req.reviewed_by = admin_id
    req.reviewed_at = datetime.now(timezone.utc)
    req.rejection_note = rejection_note
    await db.commit()
    return {"message": "Request rejected successfully"}


async def get_leave_summary(db: AsyncSession) -> list[dict]:
    today = date.today()
    result = await db.execute(
        select(LeaveWFHRequest).where(
            LeaveWFHRequest.request_type == "leave",
            LeaveWFHRequest.status == "approved",
        )
    )
    by_employee: dict[UUID, list] = defaultdict(list)
    for lv in result.scalars().all():
        by_employee[lv.employee_id].append(lv)

    rows = []
    for emp_id, leaves in by_employee.items():
        this_month_count = 0
        prev_months: dict[str, int] = defaultdict(int)
        for lv in leaves:
            days = (lv.to_date - lv.from_date).days + 1
            if lv.from_date.year == today.year and lv.from_date.month == today.month:
                this_month_count += days
            else:
                prev_months[lv.from_date.strftime("%b")] += days

        months_elapsed = today.month - 1
        total_earned = months_elapsed * LEAVES_PER_MONTH
        carry_forward = min(total_earned - sum(prev_months.values()), MAX_CARRY_FORWARD)
        balance = max(carry_forward + LEAVES_PER_MONTH - this_month_count, 0)

        rows.append({
            "employee_name": await _get_employee_name(emp_id, db),
            "this_month_leaves": this_month_count,
            "previous_months": dict(prev_months),
            "leaves_balance": balance,
        })
    return rows
