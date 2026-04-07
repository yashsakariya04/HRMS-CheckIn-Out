from sqlalchemy import select
from fastapi import HTTPException
from backend.app.models.project import Project
from backend.app.models.organization import Organization


#  CREATE PROJECT
async def create_project(data, db):
    # 1. Get organization
    org_result = await db.execute(select(Organization))
    organization = org_result.scalars().first()

    if not organization:
        raise HTTPException(status_code=400, detail="No organization found")

    # 2. Check duplicate project
    existing = await db.execute(
        select(Project).where(
            Project.organization_id == organization.id,
            Project.name == data.name,
            Project.is_active == True
        )
    )

    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Project already exists")

    # 3. Create project
    project = Project(
        name=data.name,
        description=data.description,
        organization_id=organization.id
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    return project


#  GET PROJECTS (only active ones)
async def get_projects(db):
    result = await db.execute(
        select(Project).where(Project.is_active == True)
    )
    return result.scalars().all()


#  DELETE PROJECT (soft delete)
async def delete_project(project_id, db):
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.is_active:
        raise HTTPException(status_code=400, detail="Already deleted")

    # Soft delete
    project.is_active = False

    await db.commit()

    return {"message": "Project deleted successfully"}