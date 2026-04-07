# app/routers/balances.py
"""
Leave balance routes.

GET /api/v1/balances/me          - current employee's balances
GET /api/v1/balances/{emp_id}    - admin views any employee's balances
GET /api/v1/balances/summary     - admin views all employees summary
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import date

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.employee import Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.schemas.attendance import BalanceResponse

router = APIRouter(prefix="/balances", tags=["Leave Balances"])


def _get_current_month_balances(
    db: Session,
    employee_id: str,
) -> List[EmployeeLeaveBalance]:
    """
    Fetch leave balances for current month.
    Returns list with one row per leave_type (casual, comp_off).
    """
    today = date.today()
    return db.query(EmployeeLeaveBalance).filter(
        EmployeeLeaveBalance.employee_id == employee_id,
        EmployeeLeaveBalance.year == today.year,
        EmployeeLeaveBalance.month == today.month,
    ).all()


@router.get("/me", response_model=List[BalanceResponse])
def get_my_balances(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Returns current employee's leave balances for this month.

    Frontend reads this as:
        casual   → "Leaves left: X"
        comp_off → "Comp off: X"

    Returns two rows — one per leave_type.
    """
    return _get_current_month_balances(db, current_user.id)


@router.get("/summary", response_model=List[dict])
def get_balances_summary(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """
    Admin — returns leave summary for all employees this month.
    Used in the admin Leave summary tab.
    """
    today = date.today()
    rows = db.query(EmployeeLeaveBalance).filter(
        EmployeeLeaveBalance.year == today.year,
        EmployeeLeaveBalance.month == today.month,
    ).all()
    return [
        {
            "employee_id": r.employee_id,
            "leave_type": r.leave_type,
            "closing_balance": float(r.closing_balance),
            "used": float(r.used),
        }
        for r in rows
    ]


@router.get("/{emp_id}", response_model=List[BalanceResponse])
def get_employee_balances(
    emp_id: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """Admin — view any employee's leave balances."""
    return _get_current_month_balances(db, emp_id)