"""
app/services/superadmin_service.py — Superadmin Business Logic
==============================================================
Handles listing all users and toggling admin role for any employee.
Superadmin cannot promote/demote another superadmin.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models.employee import Department, Employee


async def list_all_users(db) -> list:
    """Return all employees and admins (excludes superadmins from being modified,
    but includes them in the list for visibility)."""
    result = await db.execute(
        select(Employee, Department.name)
        .outerjoin(Department, Department.id == Employee.department_id)
        .order_by(Employee.role, Employee.email)
    )
    rows = result.all()
    return [
        {
            "id": emp.id,
            "email": emp.email,
            "full_name": emp.full_name,
            "designation": emp.designation,
            "department_name": dept_name,
            "role": emp.role,
            "is_active": emp.is_active,
        }
        for emp, dept_name in rows
    ]


async def promote_to_admin(employee_id: UUID, db, redis=None) -> dict:
    """Set role = 'admin' for the given employee."""
    emp = await _get_non_superadmin(employee_id, db)
    if emp.role == "admin":
        raise HTTPException(status_code=400, detail="Employee is already an admin")
    emp.role = "admin"
    await db.commit()
    if redis:
        await redis.delete(f"emp:{employee_id}")
    return {"message": f"{emp.email} promoted to admin"}


async def demote_to_employee(employee_id: UUID, db, redis=None) -> dict:
    """Set role = 'employee' for the given admin."""
    emp = await _get_non_superadmin(employee_id, db)
    if emp.role == "employee":
        raise HTTPException(status_code=400, detail="User is already an employee")
    emp.role = "employee"
    await db.commit()
    if redis:
        await redis.delete(f"emp:{employee_id}")
    return {"message": f"{emp.email} demoted to employee"}


async def _get_non_superadmin(employee_id: UUID, db) -> Employee:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalars().first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.role == "superadmin":
        raise HTTPException(status_code=403, detail="Cannot modify another superadmin")
    return emp
