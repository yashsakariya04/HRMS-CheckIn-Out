# app/routers/projects.py
"""
Projects routes.

GET /api/v1/projects - returns active projects for the dropdown
POST /api/v1/projects - admin creates a new project
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.employee import Employee
from app.models.project import Project
from app.schemas.attendance import ProjectResponse
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/projects", tags=["Projects"])


class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


@router.get("", response_model=List[ProjectResponse])
def get_projects(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Returns all active projects for the check-in form dropdown.
    Any logged-in employee can call this.
    """
    projects = db.query(Project).filter(
        Project.organization_id == current_user.organization_id,
        Project.is_active == True,
    ).order_by(Project.name).all()
    return projects


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreateRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin),
):
    """
    Admin creates a new project.
    It will appear in the dropdown immediately after creation.
    """
    project = Project(
        organization_id=current_user.organization_id,
        name=body.name,
        description=body.description,
        is_active=True,
    )
    db.add(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this name already exists in your organization.",
        )
    db.refresh(project)
    return project