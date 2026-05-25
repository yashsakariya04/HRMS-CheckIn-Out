"""
app/routers/balances.py — Leave Balance API Endpoints
======================================================
Endpoints for querying leave balances.

GET /api/v1/balances/me          — Employee views their own current balance.
GET /api/v1/balances/{emp_id}    — Admin views any employee's current balance.

Both endpoints return the same structure:
  [
    {
      "leave_type":       "casual" | "comp_off",
      "year":             int,
      "month":            int,
      "opening_balance":  float,   ← from the latest ledger row
      "accrued":          float,   ← from the latest ledger row
      "used":             float,   ← from the latest ledger row
      "adjusted":         float,   ← from the latest ledger row
      "closing_balance":  float,   ← REAL-TIME value (replaces ledger closing)
    },
    ...
  ]

The closing_balance returned is always the real-time virtual balance from
balance_service.compute_realtime_balance(), which accounts for:
  • leaves approved after the last rollover ran (current month),
  • leaves approved for future months (next-month leave gap fixed),
  • the comp_off-first priority chain.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.services.balance_service import compute_realtime_balance, get_balance_rows

router = APIRouter(prefix="/balances", tags=["Leave Balances"])


async def _build_balance_response(db, employee_id) -> List[dict]:
    # Sequential — SQLAlchemy AsyncSession does not allow concurrent queries on the same session
    rows = await get_balance_rows(db, employee_id)
    realtime = await compute_realtime_balance(db, employee_id)

    if rows:
        return [
            {
                "leave_type": row.leave_type,
                "year": row.year,
                "month": row.month,
                "opening_balance": float(row.opening_balance),
                "accrued": float(row.accrued),
                "used": float(row.used),
                "adjusted": float(row.adjusted),
                "closing_balance": (
                    realtime["casual_balance"]
                    if row.leave_type == "casual"
                    else realtime["comp_off_balance"]
                ),
            }
            for row in rows
        ]

    from datetime import date
    today = date.today()
    return [
        {
            "leave_type": "casual",
            "year": today.year,
            "month": today.month,
            "opening_balance": 0.0,
            "accrued": 1.0,
            "used": realtime["casual_used"],
            "adjusted": 0.0,
            "closing_balance": realtime["casual_balance"],
        },
        {
            "leave_type": "comp_off",
            "year": today.year,
            "month": today.month,
            "opening_balance": 0.0,
            "accrued": 0.0,
            "used": realtime["comp_off_used"],
            "adjusted": 0.0,
            "closing_balance": realtime["comp_off_balance"],
        },
    ]


@router.get("/me")
async def get_my_balances(
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Return the logged-in employee's current leave balances (real-time)."""
    return await _build_balance_response(db, current_user.id)


@router.get("/{emp_id}")
async def get_employee_balances(
    emp_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """Admin: return any employee's current leave balances (real-time)."""
    return await _build_balance_response(db, emp_id)





