"""
app/routers/reporting.py — Admin Reporting API Endpoints
=========================================================
Provides admin-only endpoints for viewing detailed employee attendance reports.

Endpoints:
  GET /api/v1/reporting/employees           — List all employees (for dropdown)
  GET /api/v1/reporting/{employee_id}       — Full attendance report for one employee
  GET /api/v1/reporting/{employee_id}/csv   — Download the report as a CSV file
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.schemas.reporting import EmployeeDropdownItem, ReportingResponse
from app.services.reporting_service import (
    get_all_employees,
    get_employee_report,
    get_employee_report_csv,
)

router = APIRouter(prefix="/reporting", tags=["Reporting"])


@router.get("/employees", response_model=list[EmployeeDropdownItem])
async def employee_dropdown(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: return all active employees for the report selector dropdown.
    Sorted alphabetically by name.
    """
    return await get_all_employees(db)


@router.get("/{employee_id}", response_model=ReportingResponse)
async def employee_report(
    employee_id: UUID,
    whole_month: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: return the attendance report for a specific employee.

    whole_month=False (default) → only current month's sessions
    whole_month=True            → all sessions ever recorded

    Response includes average daily hours and a list of attendance records.
    """
    return await get_employee_report(employee_id, whole_month, db)


@router.get("/{employee_id}/csv", response_class=StreamingResponse)
async def employee_report_csv(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: download the full attendance report for an employee as a CSV file.
    Filename format: report_<employee_name>_<Month_Year>.csv
    """
    return await get_employee_report_csv(employee_id, db)
