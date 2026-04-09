from collections import defaultdict
from datetime import date, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave_wfh_request import LeaveWFHRequest
from app.schemas.leaves import CurrentMonthLeaves, LeavesResponse, PreviousMonthLeaves


async def get_my_leaves(db: AsyncSession, employee_id) -> LeavesResponse:
    today = date.today()

    result = await db.execute(
        select(LeaveWFHRequest).where(
            LeaveWFHRequest.employee_id == employee_id,
            LeaveWFHRequest.status == "approved",
            LeaveWFHRequest.request_type == "leave",
        )
    )
    rows = result.scalars().all()

    all_dates: set[date] = set()
    for req in rows:
        current = req.from_date
        while current <= req.to_date:
            all_dates.add(current)
            current += timedelta(days=1)

    current_month_dates: List[date] = []
    previous_dates: List[date] = []

    for d in all_dates:
        if d.year == today.year and d.month == today.month:
            current_month_dates.append(d)
        elif d < today.replace(day=1):
            previous_dates.append(d)

    current_month = CurrentMonthLeaves(
        month=today.month,
        year=today.year,
        dates=sorted(d.isoformat() for d in current_month_dates),
    )

    grouped: dict[tuple, List[date]] = defaultdict(list)
    for d in previous_dates:
        grouped[(d.year, d.month)].append(d)

    previous_months = [
        PreviousMonthLeaves(
            month=month,
            year=year,
            total_days=len(dates),
            dates=sorted(d.isoformat() for d in dates),
        )
        for (year, month), dates in sorted(grouped.items(), reverse=True)
    ]

    return LeavesResponse(current_month=current_month, previous_months=previous_months)
