"""
app/services/add_project_service.py — Project Management Business Logic
=======================================================================
Handles creating, listing, and soft-deleting projects.

Non-technical summary:
----------------------
Projects are what employees assign their daily tasks to (e.g. "Website Redesign").
Admins manage the project list. Projects are never hard-deleted — they are
soft-deleted (is_active = False) so historical task entries remain valid.
"""

from fastapi import HTTPException
from sqlalchemy import select

from app.models.organization import Organization
from app.models.project import Project


async def create_project(data, db) -> Project:
    """
    Create a new project for the organization.

    Args:
        data: ProjectCreate with name and optional description.
        db:   Async database session.

    Returns:
        The newly created Project ORM object.

    Raises:
        400 — No organization found.
        400 — A project with the same name already exists (and is active).
    """
    org_result = await db.execute(select(Organization))
    organization = org_result.scalars().first()
    if not organization:
        raise HTTPException(status_code=400, detail="No organization found")

    # Check for duplicate active project name within the organization
    existing = await db.execute(
        select(Project).where(
            Project.organization_id == organization.id,
            Project.name == data.name,
            Project.is_active == True,
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Project already exists")

    project = Project(
        name=data.name,
        description=data.description,
        organization_id=organization.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_projects(db) -> list:
    """
    Return all active projects.

    Soft-deleted projects (is_active = False) are excluded.
    Used to populate the project dropdown when employees log tasks.

    Args:
        db: Async database session.
    """
    result = await db.execute(select(Project).where(Project.is_active == True))
    return result.scalars().all()


async def delete_project(project_id, db) -> dict:
    """
    Soft-delete a project by setting is_active = False.

    Historical task entries referencing this project are preserved.
    The project will no longer appear in the task dropdown.

    Args:
        project_id: UUID of the project to deactivate.
        db:         Async database session.

    Returns:
        Success message dict.

    Raises:
        404 — Project not found.
        400 — Project is already deleted.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.is_active:
        raise HTTPException(status_code=400, detail="Already deleted")

    project.is_active = False
    await db.commit()
    return {"message": "Project deleted successfully"}
