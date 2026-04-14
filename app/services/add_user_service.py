"""
app/services/add_user_service.py — Employee Management Business Logic
=====================================================================
Handles creating, updating, and deactivating employee records.

Non-technical summary:
----------------------
Admins use this service to manage the employee roster:
  - create_employee : Registers a new employee so they can log in via Google.
  - list_employees  : Returns all employees (active and inactive) for admin view.
  - update_profile  : Lets an employee update their display name and photo.
  - delete_employee : Deactivates an employee (soft delete — data is preserved).
"""

import uuid
from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models.employee import Department, Employee
from app.models.employee_leave_balance import EmployeeLeaveBalance
from app.models.organization import Organization

async def list_employees(db) -> list:
    result = await db.execute(
        select(Employee, Department.name)
        .outerjoin(Department, Department.id == Employee.department_id)
        .where(Employee.role == "employee", Employee.is_active == True)
        .order_by(Employee.email)
    )
    rows = result.all()
    return [
        {
            "id": emp.id,
            "email": emp.email,
            "designation": emp.designation,
            "department_name": dept_name,
            "is_active": emp.is_active,
        }
        for emp, dept_name in rows
    ]

# async def list_employees(db) -> list:
#     result = await db.execute(
#         select(Employee, Department.name)
#         .outerjoin(Department, Department.id == Employee.department_id)
#         .order_by(Employee.email)
#     )
#     rows = result.all()
#     return [
#         {
#             "id": emp.id,
#             "email": emp.email,
#             "designation": emp.designation,
#             "department_name": dept_name,
#             "is_active": emp.is_active,
#         }
#         for emp, dept_name in rows
#     ]


async def create_employee(data, db) -> Employee:
    """
    Register a new employee in the system.

    Automatically assigns the employee to the organization found in the database
    (single-org setup). The employee can log in via Google once their email
    is registered here.

    Args:
        data: CreateEmployeeRequest with email, department_id, designation.
        db:   Async database session.

    Returns:
        The newly created Employee ORM object.

    Raises:
        400 — Employee with this email already exists.
        400 — No organization found in the database.
    """
    # Prevent duplicate employees
    existing = await db.execute(select(Employee).where(Employee.email == data.email))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Employee already exists")

    # Get the single organization (single-tenant setup)
    org_result = await db.execute(select(Organization))
    organization = org_result.scalars().first()
    if not organization:
        raise HTTPException(status_code=400, detail="No organization found")

    dept_result = await db.execute(
        select(Department).where(
            Department.organization_id == organization.id,
            Department.name == data.department_name
        )
    )
    department = dept_result.scalars().first()
    if not department:
        # Auto-create the department if it doesn't exist yet
        department = Department(organization_id=organization.id, name=data.department_name)
        db.add(department)
        await db.flush()
        
    employee = Employee(
        email=data.email,
        organization_id=organization.id,
        department_id=department.id,
        designation=data.designation,
    )
    db.add(employee)
    await db.flush()  # get employee.id before creating balance rows

    # Seed leave balance rows for the current month so the new employee
    # immediately has 1 casual leave available instead of waiting for
    # the monthly rollover job to run on the 1st.
    today = date.today()
    initial_balances = [
        EmployeeLeaveBalance(
            employee_id=employee.id,
            leave_type="casual",
            year=today.year,
            month=today.month,
            opening_balance=0.0,
            accrued=1.0,
            used=0.0,
            adjusted=0.0,
            closing_balance=1.0,
        ),
        EmployeeLeaveBalance(
            employee_id=employee.id,
            leave_type="comp_off",
            year=today.year,
            month=today.month,
            opening_balance=0.0,
            accrued=0.0,
            used=0.0,
            adjusted=0.0,
            closing_balance=0.0,
        ),
    ]
    db.add_all(initial_balances)

    await db.commit()
    await db.refresh(employee)
    return employee


async def update_profile(user: Employee, data, db) -> dict:
    """
    Update the employee's own profile (name and/or photo URL).

    Only updates fields that are provided (non-None).

    Args:
        user: The currently authenticated Employee ORM object.
        data: UpdateProfileRequest with full_name and optional photo_url.
        db:   Async database session.

    Returns:
        Success message dict.
    """
    if data.full_name:
        user.full_name = data.full_name
    if data.photo_url:
        user.photo_url = data.photo_url

    await db.commit()
    return {"message": "Profile updated"}


async def delete_employee(employee_id: UUID, db) -> dict:
    """
    Soft-delete an employee by setting is_active = False.

    The employee's data (attendance, tasks, leave history) is preserved.
    They can no longer log in after deactivation.

    Args:
        employee_id: UUID of the employee to deactivate.
        db:          Async database session.

    Returns:
        Success message dict.

    Raises:
        404 — Employee not found.
        400 — Employee is already deactivated.
    """
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    employee = result.scalars().first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if not employee.is_active:
        raise HTTPException(status_code=400, detail="Employee already deactivated")

    employee.is_active = False
    await db.commit()
    return {"message": "Employee deactivated successfully"}
