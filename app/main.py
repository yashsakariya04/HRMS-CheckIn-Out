# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth as auth_router
from app.routers import attendance as attendance_router
from app.routers import add_project_api
from app.routers import add_holiday_api 
from app.routers import balances as balances_router
from app.routers import tasks as tasks_router
from app.routers import add_user_api
from app.routers import requests_Emp as requests_router
from app.routers import calendar as calendar_router
from app.routers import leaves as leaves_router
from app.routers import reporting 
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.jobs.leave_rollover import run_leave_rollover
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_leave_rollover, "cron", day=1, hour=0, minute=5)
    scheduler.start()
    yield
    scheduler.shutdown()
    
app = FastAPI(lifespan=lifespan ,title="HRMS Backend API", version="1.0.0", docs_url="/docs")    
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router,       prefix="/api/v1")
app.include_router(attendance_router.router, prefix="/api/v1")
app.include_router(tasks_router.router,      prefix="/api/v1")
app.include_router(balances_router.router,   prefix="/api/v1")
app.include_router(requests_router.router,   prefix="/api/v1")
app.include_router(calendar_router.router,   prefix="/api/v1")
app.include_router(leaves_router.router,     prefix="/api/v1")
app.include_router(reporting.router,  prefix="/api/v1")
app.include_router(add_user_api.router,   prefix="/api/v1")
app.include_router(add_project_api.router,   prefix="/api/v1")
app.include_router(add_holiday_api.router,   prefix="/api/v1")

@app.get("/health", tags=["Health"])
def health():
    """Health check — no auth required."""
    return {"status": "ok"}
