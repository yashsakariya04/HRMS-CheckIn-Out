from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.services.tracker import analytics_service

router = APIRouter(prefix="/tracker/analytics", tags=["Tracker — Analytics"])


@router.get("/dashboard")
async def dashboard_stats(
    admin: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_dashboard_stats(db, admin.organization_id)
