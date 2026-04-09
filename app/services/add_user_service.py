# services/employee_service.py
from sqlalchemy import select
from fastapi import HTTPException
from app.models.employee import Employee
import uuid
from app.models.organization import Organization
from uuid import UUID

async def create_employee(data, db):

    # Check existing employee
    existing = await db.execute(
        select(Employee).where(Employee.email == data.email)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Employee already exists")

    # Get organization (only one exists)
    org_result = await db.execute(select(Organization))
    organization = org_result.scalars().first()

    if not organization:
        raise HTTPException(status_code=400, detail="No organization found")

    # Create employee
    employee = Employee(
        email=data.email,
        organization_id=organization.id,  
        department_id=data.department_id,
        designation=data.designation,
    )

    db.add(employee)
    await db.commit()
    await db.refresh(employee)

    return employee


async def update_profile(user, data, db):
    # Allow user to update name freely
    if data.full_name:
        user.full_name = data.full_name

    # Allow user to update photo freely
    if data.photo_url:
        user.photo_url = data.photo_url

    await db.commit()

    return {"message": "Profile updated"}


async def delete_employee(employee_id: UUID, db):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalars().first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not employee.is_active:
        raise HTTPException(status_code=400, detail="Employee already deactivated")

    employee.is_active = False
    await db.commit()

    return {"message": "Employee deactivated successfully"}