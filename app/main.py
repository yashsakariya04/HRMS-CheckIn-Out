"""
HRMS Backend — Application Entry Point
=======================================
This is the main file that starts the entire backend application.

What is HRMS?
-------------
HRMS stands for Human Resource Management System. This backend handles:
  - Employee login (via Google OAuth)
  - Daily attendance (check-in / check-out)
  - Task logging (what work was done each day)
  - Leave and WFH requests (apply, approve, reject)
  - Leave balance tracking (casual leave, comp-off)
  - Holiday calendar
  - Admin reporting

How it works (non-technical summary):
--------------------------------------
Think of this file as the "reception desk" of the application.
It registers all the different departments (routers) and makes sure
the building (app) is open for business. It also starts a background
clock (scheduler) that automatically runs a monthly leave rollover
on the 1st of every month.

API base URL: /api/v1
Interactive docs: /docs  (Swagger UI — open in browser when server is running)
"""

from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.jobs.leave_rollover import run_leave_rollover
from app.jobs.tracker_jobs import run_deadline_reminders, run_overdue_flagging
from app.routers import (
    attendance as attendance_router,
    auth as auth_router,
    balances as balances_router,
    calendar as calendar_router,
    leaves as leaves_router,
    reporting,
    requests_Emp as requests_router,
    tasks as tasks_router,
)
from app.routers import add_holiday_api, add_project_api, add_user_api, announcement_api
from app.routers import superadmin as superadmin_router
from app.routers.tracker import tasks as tracker_tasks
from app.routers.tracker import comments as tracker_comments
from app.routers.tracker import extensions as tracker_extensions
from app.routers.tracker import files as tracker_files
from app.routers.tracker import notifications as tracker_notifications
from app.routers.tracker import subtasks as tracker_subtasks
from app.routers.tracker import similar_tasks as tracker_similar_tasks
from app.routers import leave_notifications as leave_notifications_router


@asynccontextmanager
async def lifespan(app):
    """
    Application lifespan manager — runs code on startup and shutdown.

    On startup:
        Starts the APScheduler background scheduler.
        Schedules the monthly leave rollover job to run on the 1st of
        every month at 00:05 AM (server time).

    On shutdown:
        Gracefully stops the scheduler so no jobs are left hanging.
    """
    scheduler = AsyncIOScheduler()
    # Run leave rollover on the 1st of every month at 00:05
    scheduler.add_job(run_leave_rollover, "cron", day=1, hour=0, minute=5)
    scheduler.add_job(run_deadline_reminders, "cron", hour=8, minute=0)   # 8 AM daily
    scheduler.add_job(run_overdue_flagging,   "cron", hour=0, minute=30)  # 12:30 AM daily
    scheduler.start()
    yield  # Application runs here
    scheduler.shutdown()

# ── FastAPI app instance ──────────────────────────────────────────────────────
app = FastAPI(
    lifespan=lifespan,
    title="HRMS Backend API",
    version="1.0.0",
    docs_url="/docs",
)

# ── CORS middleware ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register all routers under /api/v1 ───────────────────────────────────────
# Each router handles a specific feature area of the HRMS.
app.include_router(auth_router.router,       prefix="/api/v1")  # Login, logout, token refresh
app.include_router(attendance_router.router, prefix="/api/v1")  # Check-in, check-out, sessions
app.include_router(tasks_router.router,      prefix="/api/v1")  # Daily task logging
app.include_router(balances_router.router,   prefix="/api/v1")  # Leave balance queries
app.include_router(requests_router.router,   prefix="/api/v1")  # Leave/WFH request CRUD
app.include_router(calendar_router.router,   prefix="/api/v1")  # Monthly leave calendar
app.include_router(leaves_router.router,     prefix="/api/v1")  # Employee leave history
app.include_router(reporting.router,         prefix="/api/v1")  # Admin attendance reports
app.include_router(add_user_api.router,      prefix="/api/v1")  # Admin: add/remove employees
app.include_router(add_project_api.router,   prefix="/api/v1")  # Admin: manage projects
app.include_router(add_holiday_api.router,   prefix="/api/v1")  # Admin: manage holidays
app.include_router(superadmin_router.router, prefix="/api/v1")  # Superadmin: role management
app.include_router(announcement_api.router,   prefix="/api/v1")  # Announcement endpoints
app.include_router(ai_router.router,          prefix="/api/v1")  # This is not used by the backend it is just for testing purpose 
app.include_router(tracker_tasks.router,        prefix="/api/v1")  # Tracker: tasks
app.include_router(tracker_comments.router,     prefix="/api/v1")  # Tracker: comments
app.include_router(tracker_files.router,        prefix="/api/v1")  # Tracker: file uploads
app.include_router(tracker_extensions.router,   prefix="/api/v1")  # Tracker: extensions
app.include_router(tracker_notifications.router,prefix="/api/v1")  # Tracker: notifications
app.include_router(tracker_subtasks.router,     prefix="/api/v1")  # Tracker: subtasks
app.include_router(tracker_similar_tasks.router, prefix="/api/v1")  # Tracker: similar tasks panel
app.include_router(leave_notifications_router.router, prefix="/api/v1")  # Leave notifications


@app.get("/health", tags=["Health"])
def health():
    """
    Health check endpoint — no authentication required.

    Used by load balancers and monitoring tools to verify the server is alive.
    Returns: {"status": "ok"}
    """
    return {"status": "ok"}
