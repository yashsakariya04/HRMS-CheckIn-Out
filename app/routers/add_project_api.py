"""
app/routers/add_project_api.py — Project Management API Endpoints
=================================================================
Admin endpoints for managing the list of projects employees can log tasks against.

Endpoints:
  POST   /api/v1/project/add        — Admin creates a new project
  GET    /api/v1/project/           — List all active projects (used for task dropdown)
  DELETE /api/v1/project/{id}       — Admin soft-deletes a project
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.schemas.add_project import ProjectCreate, ProjectResponse
from app.services.add_project_service import create_project, delete_project, get_projects

router = APIRouter(prefix="/project", tags=["Project"])


@router.post("/add", response_model=ProjectResponse)
async def add_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: create a new project.
    Returns 400 if a project with the same name already exists in the organization.
    """
    return await create_project(data, db)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
):
    """
    Return all active projects. No authentication required.
    Used to populate the project dropdown when employees log tasks.
    """
    return await get_projects(db)


@router.delete("/{project_id}")
async def remove_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin only: soft-delete a project (sets is_active = False).
    The project disappears from dropdowns but historical task entries are preserved.
    Returns 404 if not found, 400 if already deleted.
    """
    return await delete_project(project_id, db)
