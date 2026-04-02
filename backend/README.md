# HRMS CheckIn Out

A backend system for an HR Management application that handles employee attendance, task reporting, leave management, and admin oversight. The frontend for this project already exists as a React and TypeScript application. This repository documents and will contain the Python FastAPI backend that powers it.

---

## What This Project Does

The system allows employees to check in and check out of work each day, log the tasks they completed against specific projects, and submit requests for leave, work from home days, missing time corrections, and compensatory off. Administrators can view attendance and task reports for any employee, download monthly reports as CSV files, review leave balances across the team, and approve or reject all employee requests.

---

## Project Structure

```
HRMS/backend/
        app/
            main.py
            config.py
            database.py
            models/
            schemas/
            routers/
            services/
            jobs/
        alembic/
            env.py
            versions/
        tests/
        .env.example
        requirements.txt
        Dockerfile
        docker-compose.yml
```

---

## Tech Stack

**Language:** Python 3.11
**Framework:** FastAPI
**Database:** PostgreSQL 16
**ORM:** SQLAlchemy 2.x with async support
**Migrations:** Alembic
**Authentication:** JWT tokens using RS256 signing
**Password Hashing:** Argon2id via passlib
**Cache and Rate Limiting:** Redis
**Job Scheduler:** APScheduler
**Containerization:** Docker and Docker Compose

---

## Prerequisites

Before running this project you need the following installed on your machine.

Docker and Docker Compose
Python 3.11 or later
OpenSSL (for generating JWT signing keys)

---

## Getting Started

**Step 1. Clone the repository**

```bash
git clone https://github.com/your-org/HRMS-CheckIn-Out.git
cd HRMS-CheckIn-Out/backend
```

**Step 2. Generate RSA keys for JWT signing**

```bash
mkdir keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

**Step 3. Set up environment variables**

```bash
cp .env.example .env
```

Open the `.env` file and fill in the values as described in the Environment Variables section below.

**Step 4. Start the database and Redis**

```bash
docker compose up -d db redis
```

**Step 5. Create a virtual environment and install dependencies**

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Step 6. Run database migrations**

```bash
alembic upgrade head
```

This creates all twelve tables and inserts the default seed data including the organization record, project list, holiday calendar, and demo employee accounts.

**Step 7. Start the API server**

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` and the auto generated documentation will be at `http://localhost:8000/docs`.

---

## Environment Variables

Below is a description of every variable in the `.env` file.

```
DATABASE_URL         Full PostgreSQL connection string for async SQLAlchemy
REDIS_URL            Redis connection string
JWT_PRIVATE_KEY_PATH Path to the private.pem file used to sign tokens
JWT_PUBLIC_KEY_PATH  Path to the public.pem file used to verify tokens
JWT_ALGORITHM        Signing algorithm, should be RS256
ACCESS_TOKEN_EXPIRE_MINUTES   How long the access token stays valid, default 15
REFRESH_TOKEN_EXPIRE_DAYS     How long the refresh token stays valid, default 7
CORS_ORIGINS         Comma separated list of allowed frontend origins
```

---

## Database

The database has twelve tables. Here is a brief description of each one.

**organizations** holds the company record and sits at the top of the data hierarchy. All other records belong to an organization.

**departments** groups employees into teams such as Engineering or Design.

**employees** is a single table for all users including administrators. The role column determines what each user can do. A value of employee gives standard access. A value of admin gives approval and reporting access. Administrators are not a separate entity.

**refresh_tokens** stores secure hashes of the long lived refresh tokens issued at login. This allows tokens to be revoked immediately when a user logs out.

**projects** holds the list of active projects that employees can tag their daily tasks against. This replaces what was previously a hardcoded list in the frontend.

**attendance_sessions** is the core table. One record is created each time an employee checks in. The check out time is filled in when they leave. The total hours worked is computed automatically by the database. Only one session is allowed per employee per day.

**task_entries** stores the individual tasks logged by an employee within a session. Each task is associated with a project and has a description and hours logged.

**leave_policies** stores the rules for how leave is accrued, including how many days are earned per month and how many unused days can be carried forward.

**employee_leave_balances** is the leave ledger. One row per employee per leave type per month tracks opening balance, accrual, usage, adjustments, and the closing balance.

**leave_wfh_requests** holds all four types of requests: leave, work from home, missing time correction, and compensatory off. Each request has a status that moves from pending to approved or rejected.

**holidays** stores company and national holidays. This replaces a hardcoded list that previously lived in the frontend code.

**audit_logs** records every sensitive admin action permanently. Records here are never updated or deleted.

---

## API Overview

All endpoints are served under the `/api/v1/` prefix. The API follows standard REST conventions and returns JSON for all responses.

**Auth:** Login, logout, token refresh, and current user profile.

**Employees:** Create, read, update, and deactivate employee accounts. Admin only except for reading your own profile.

**Attendance:** Check in, check out, fetch today's session, retrieve monthly records, and calculate average hours for the current month.

**Tasks:** Add, update, and remove task entries within an active session.

**Requests:** Submit and cancel requests as an employee. Approve or reject requests as an administrator.

**Balances:** View leave balances for yourself or any employee. View a summary across all employees.

**Projects and Holidays:** Read access for all authenticated users. Write access for administrators only.

**Reporting:** Monthly attendance data in JSON or CSV format. Leave summary for all employees.

Full interactive documentation is available at `http://localhost:8000/docs` when the server is running.

---

## Background Jobs

The backend runs four scheduled jobs automatically.

The first job runs at midnight on the first of every month and creates leave balance records for the new month for every active employee, applying the carry forward from the previous month and adding the new accrual.

The second job runs at the end of each day and flags any attendance session from that day where the employee checked in but never checked out.

The third job runs each night and removes expired and revoked refresh tokens from the database.

The fourth job runs on the last day of each month and generates a CSV summary of attendance and leave which is sent to the administrator.

---

## Running Tests

```bash
pytest tests/
```

Tests cover authentication, attendance check in and check out logic, leave request approval and side effects, and reporting accuracy.

---

## Migrations

To create a new migration after changing a model run the following command.

```bash
alembic revision --autogenerate -m "describe your change here"
alembic upgrade head
```

To roll back the most recent migration run this.

```bash
alembic downgrade -1
```

---

## Security Notes

Passwords are hashed using Argon2id and are never stored or logged in plain text. Access tokens expire in fifteen minutes. Refresh tokens expire in seven days and are stored as SHA256 hashes so the raw token is never persisted in the database. Login attempts are rate limited via Redis to protect against brute force attacks. All admin actions are recorded in the audit log.

---

## Contributing

Please create a feature branch from main for any new work. Keep commits focused and descriptive. Run the test suite before raising a pull request. Do not commit the contents of the keys folder or the .env file.

---

## License

Internal use only.
