from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies.auth import require_admin
from backend.app.dependencies.database import get_db
from backend.app.schemas.reporting import EmployeeDropdownItem, ReportingResponse
from backend.app.services.reporting_service import (
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
    return await get_all_employees(db)


@router.get("/{employee_id}", response_model=ReportingResponse)
async def employee_report(
    employee_id: UUID,
    whole_month: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    return await get_employee_report(employee_id, whole_month, db)


@router.get("/{employee_id}/csv", response_class=StreamingResponse)
async def employee_report_csv(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    return await get_employee_report_csv(employee_id, db)
