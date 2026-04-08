from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from backend.app.schemas.add_project import ProjectCreate, ProjectResponse
from backend.app.services.add_project_service import (
    create_project,
    get_projects,
    delete_project
)
from backend.app.dependencies.database import get_db
from backend.app.dependencies.auth import require_admin

router = APIRouter(prefix="/project", tags=["Project"])


# ADD PROJECT (Admin only)
@router.post("/add", response_model=ProjectResponse)
async def add_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    admin = Depends(require_admin)
):
    return await create_project(data, db)

#  GET ALL PROJECTS
@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db)
):
    return await get_projects(db)

#  DELETE PROJECT (Admin only)
@router.delete("/{project_id}")
async def remove_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin = Depends(require_admin)
):
    return await delete_project(project_id, db)    

