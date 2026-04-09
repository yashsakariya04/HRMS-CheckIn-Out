"""
Seed script — creates demo organization, departments, leave policies,
employees, leave balances, projects, and holidays.

Run ONCE after: alembic upgrade head
Command:        python seed.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.organization import Organization
from app.models.employee import Employee
from app.models.project import Project
from app.models.holiday import Holiday
from app.models.leave_policy import LeavePolicy
from app.models.employee_leave_balance import EmployeeLeaveBalance

# Use sync URL
SYNC_URL = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(bind=engine)


def seed():
    db = SessionLocal()
    try:
        print("Seeding database...\n")

        # 1. Organization
        org = db.query(Organization).filter_by(slug="infopulse").first()
        if not org:
            org = Organization(name="Infopulse", slug="infopulse")
            db.add(org)
            db.flush()
            print(f"  [+] Organization : {org.name}")
        else:
            print(f"  [=] Organization : {org.name} (already exists)")

        # 2. Departments
        from sqlalchemy import text
        dept_names = ["Engineering", "Design", "Product", "HR"]
        depts = {}
        for name in dept_names:
            result = db.execute(
                text("SELECT id FROM department WHERE name=:name AND organization_id=:org_id"),
                {"name": name, "org_id": org.id}
            ).fetchone()
            if not result:
                db.execute(
                    text("INSERT INTO department (name, organization_id) VALUES (:name, :org_id) RETURNING id"),
                    {"name": name, "org_id": org.id}
                )
                db.flush()
                result = db.execute(
                    text("SELECT id FROM department WHERE name=:name AND organization_id=:org_id"),
                    {"name": name, "org_id": org.id}
                ).fetchone()
                print(f"  [+] Department   : {name}")
            depts[name] = result[0]

        # 3. Leave Policies
        policies = [
            {"leave_type": "casual",   "days_per_month": 1, "max_carry_fwd": 1},
            {"leave_type": "sick",     "days_per_month": 1, "max_carry_fwd": 0},
            {"leave_type": "earned",   "days_per_month": 1, "max_carry_fwd": 15},
            {"leave_type": "comp_off", "days_per_month": 0, "max_carry_fwd": 3},
        ]
        for p in policies:
            existing = db.query(LeavePolicy).filter_by(
                organization_id=org.id, leave_type=p["leave_type"]
            ).first()
            if not existing:
                db.add(LeavePolicy(organization_id=org.id, **p))
                print(f"  [+] Leave policy : {p['leave_type']}")
        db.flush()

        # 4. Employees
        employees_data = [
            {"email": "yash.infopulsetech@gmail.com",    "full_name": "Yash Sakariya", "designation": "HR Manager",               "role": "admin",    "department": "HR"},
            {"email": "nimisha.infopulsetech@gmail.com", "full_name": "Nimisha",        "designation": "Senior Backend Developer", "role": "employee", "department": "Engineering"},
            {"email": "john.infopulsetech@gmail.com",    "full_name": "John",           "designation": "Frontend Developer",       "role": "employee", "department": "Engineering"},
            {"email": "jane.infopulsetech@gmail.com",    "full_name": "Jane",           "designation": "UI Designer",              "role": "employee", "department": "Design"},
        ]

        created_employees = []
        for data in employees_data:
            emp = db.query(Employee).filter_by(email=data["email"]).first()
            if not emp:
                emp = Employee(
                    organization_id=org.id,
                    department_id=depts[data["department"]],
                    email=data["email"],
                    full_name=data["full_name"],
                    designation=data["designation"],
                    role=data["role"],
                    is_active=True,
                )
                db.add(emp)
                db.flush()
                print(f"  [+] Employee     : {emp.full_name} <{emp.email}> ({emp.role})")
            else:
                print(f"  [=] Employee     : {emp.full_name} (already exists)")
            created_employees.append(emp)

        # 5. Leave Balances
        now = datetime.now()
        for emp in created_employees:
            if emp.role == "admin":
                continue
            for leave_type, accrued in [("casual", 1), ("sick", 1), ("earned", 1), ("comp_off", 0)]:
                exists = db.query(EmployeeLeaveBalance).filter_by(
                    employee_id=emp.id, year=now.year, month=now.month, leave_type=leave_type
                ).first()
                if not exists:
                    db.add(EmployeeLeaveBalance(
                        employee_id=emp.id,
                        year=now.year, month=now.month,
                        leave_type=leave_type,
                        opening_balance=0, accrued=accrued,
                        used=0, adjusted=0, closing_balance=accrued,
                    ))
                    print(f"  [+] Balance      : {emp.full_name} — {leave_type}")

        # 6. Projects
        for name in ["Mobile App", "Backend API", "Admin Dashboard", "Internal Tools"]:
            proj = db.query(Project).filter_by(name=name, organization_id=org.id).first()
            if not proj:
                db.add(Project(name=name, organization_id=org.id, is_active=True))
                print(f"  [+] Project      : {name}")

        # 7. Holidays
        current_year = date.today().year
        for h in [
            {"name": "Republic Day",     "date": date(current_year, 1, 26)},
            {"name": "Holi",             "date": date(current_year, 3, 17)},
            {"name": "Ram Navami",       "date": date(current_year, 4, 6)},
            {"name": "Independence Day", "date": date(current_year, 8, 15)},
            {"name": "Gandhi Jayanti",   "date": date(current_year, 10, 2)},
            {"name": "Diwali",           "date": date(current_year, 10, 20)},
            {"name": "Christmas",        "date": date(current_year, 12, 25)},
        ]:
            exists = db.query(Holiday).filter_by(organization_id=org.id, holiday_date=h["date"]).first()
            if not exists:
                db.add(Holiday(organization_id=org.id, name=h["name"], holiday_date=h["date"], holiday_type="national"))
                print(f"  [+] Holiday      : {h['name']}")

        db.commit()
        print("\n" + "─" * 55)
        print("Seeding complete!")
        print("─" * 55)
        print("\nRegistered accounts:")
        for data in employees_data:
            print(f"  {data['role']:8} | {data['email']}")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
