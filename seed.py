# seed.py
"""
Seed script — creates demo organization, projects, holidays, and employees.
Run once after alembic upgrade head:
    python seed.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from app.database import SessionLocal
from app.models.organization import Organization
from app.models.employee import Department, Employee
from app.models.project import Project
from app.models.holiday import Holiday
from app.models.leave_policy import LeavePolicy
from app.models.employee_leave_balance import EmployeeLeaveBalance


def seed():
    db = SessionLocal()
    try:
        print("Seeding database...")

        # ── 1. Organization ────────────────────────────────────────────────
        org = db.query(Organization).filter_by(name="Infopulse").first()
        if not org:
            org = Organization(
                name="Infopulse",
                domain="infopulse.com",
                is_active=True,
            )
            db.add(org)
            db.flush()  # flush to get org.id before using it below
            print(f"  Created organization: {org.name} (id={org.id})")
        else:
            print(f"  Organization already exists: {org.name}")

        # ── 2. Departments ─────────────────────────────────────────────────
        dept_names = ["Engineering", "Design", "Product", "HR"]
        depts = {}
        for name in dept_names:
            dept = db.query(Department).filter_by(
                name=name, organization_id=org.id
            ).first()
            if not dept:
                dept = Department(name=name, organization_id=org.id)
                db.add(dept)
                db.flush()
                print(f"  Created department: {name}")
            depts[name] = dept

        # ── 3. Leave Policies ──────────────────────────────────────────────
        policies = [
            {"leave_type": "casual",  "accrual_per_month": 1, "max_carry_forward": 1},
            {"leave_type": "comp_off", "accrual_per_month": 0, "max_carry_forward": 3},
        ]
        for p in policies:
            existing = db.query(LeavePolicy).filter_by(
                organization_id=org.id, leave_type=p["leave_type"]
            ).first()
            if not existing:
                policy = LeavePolicy(organization_id=org.id, **p)
                db.add(policy)
                print(f"  Created leave policy: {p['leave_type']}")

        db.flush()

        # ── 4. Employees ───────────────────────────────────────────────────
        # IMPORTANT: Use the real Google email addresses your team logs in with
        employees_data = [
            {
                "email": "yash.infopulsetech@gmail.com",
                "full_name": "Admin User",
                "job_title": "HR Manager",
                "role": "admin",
                "department": "HR",
            },
            {
                "email": "nimisha.infopulsetech@gmail.com",
                "full_name": "Nimisha",
                "job_title": "Senior Backend developer",
                "role": "employee",
                "department": "Engineering",
            },
            {
                "email": "john.infopulsetech@gmail.com",
                "full_name": "John",
                "job_title": "Frontend developer",
                "role": "employee",
                "department": "Engineering",
            },
            {
                "email": "sakariyayash04@gmail.com",  # ← your real Google email
                "full_name": "Yash Sakariya",
                "job_title": "HR Manager",
                "role": "admin",
                "department": "HR",
            },
            {
                "email": "jane.infopulsetech@gmail.com",
                "full_name": "Jane",
                "job_title": "UI Designer",
                "role": "employee",
                "department": "Design",
            },
        ]

        created_employees = []
        for emp_data in employees_data:
            emp = db.query(Employee).filter_by(email=emp_data["email"]).first()
            if not emp:
                emp = Employee(
                    organization_id=org.id,
                    department_id=depts[emp_data["department"]].id,
                    email=emp_data["email"],
                    full_name=emp_data["full_name"],
                    job_title=emp_data["job_title"],
                    role=emp_data["role"],
                    is_active=True,
                )
                db.add(emp)
                db.flush()
                print(f"  Created employee: {emp.full_name} ({emp.role})")
            created_employees.append(emp)

        # ── 5. Leave Balances (current month for each employee) ────────────
        from datetime import datetime
        now = datetime.now()
        for emp in created_employees:
            if emp.role == "admin":
                continue  # admin does not track leaves
            for leave_type in ["casual", "comp_off"]:
                existing = db.query(EmployeeLeaveBalance).filter_by(
                    employee_id=emp.id,
                    year=now.year,
                    month=now.month,
                    leave_type=leave_type,
                ).first()
                if not existing:
                    balance = EmployeeLeaveBalance(
                        employee_id=emp.id,
                        year=now.year,
                        month=now.month,
                        leave_type=leave_type,
                        opening_balance=0,
                        accrued=1 if leave_type == "casual" else 0,
                        used=0,
                        adjusted=0,
                        closing_balance=1 if leave_type == "casual" else 0,
                    )
                    db.add(balance)
                    print(f"  Created {leave_type} balance for {emp.full_name}")

        # ── 6. Projects ────────────────────────────────────────────────────
        project_names = [
            "UnbounX Mobile",
            "Backend API",
            "Admin Dashboard",
            "Internal Tools",
        ]
        for name in project_names:
            proj = db.query(Project).filter_by(
                name=name, organization_id=org.id
            ).first()
            if not proj:
                proj = Project(
                    name=name,
                    organization_id=org.id,
                    is_active=True,
                )
                db.add(proj)
                print(f"  Created project: {name}")

        # ── 7. Holidays (2026) ─────────────────────────────────────────────
        holidays_data = [
            {"name": "Republic Day",      "date": date(2026, 1, 26)},
            {"name": "Holi",              "date": date(2026, 3, 17)},
            {"name": "Ram Navami",        "date": date(2026, 4, 6)},
            {"name": "Independence Day",  "date": date(2026, 8, 15)},
            {"name": "Gandhi Jayanti",    "date": date(2026, 10, 2)},
            {"name": "Diwali",            "date": date(2026, 10, 20)},
            {"name": "Christmas",         "date": date(2026, 12, 25)},
        ]
        for h in holidays_data:
            existing = db.query(Holiday).filter_by(
                organization_id=org.id,
                holiday_date=h["date"],
            ).first()
            if not existing:
                holiday = Holiday(
                    organization_id=org.id,
                    name=h["name"],
                    holiday_date=h["date"],
                    year=h["date"].year,
                )
                db.add(holiday)
                print(f"  Created holiday: {h['name']}")

        # ── Commit everything ──────────────────────────────────────────────
        db.commit()
        print("\nSeeding complete!")
        print("\nEmployee emails registered in system:")
        for e in employees_data:
            print(f"  {e['role']:8} | {e['email']}")
        print("\nIMPORTANT: These emails must match the Google accounts")
        print("you use to log in. Update them in seed.py if needed.")

    except Exception as e:
        db.rollback()
        print(f"\nSeed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()