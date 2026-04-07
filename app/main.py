# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth as auth_router
from app.routers import attendance as attendance_router
from app.routers import projects as projects_router
from app.routers import holidays as holidays_router
from app.routers import balances as balances_router
from app.routers import tasks as tasks_router
from app.routers import add_user_api as add_user_router
from app.routers import requests_Emp as requests_router
from app.routers import calendar as calendar_router
from app.routers import leaves as leaves_router

app = FastAPI(title="HRMS Backend API", version="1.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router,       prefix="/api/v1")
app.include_router(attendance_router.router, prefix="/api/v1")
app.include_router(projects_router.router,   prefix="/api/v1")
app.include_router(holidays_router.router,   prefix="/api/v1")
app.include_router(balances_router.router,   prefix="/api/v1")
app.include_router(tasks_router.router,      prefix="/api/v1")
app.include_router(add_user_router.router,   prefix="/api/v1")
app.include_router(requests_router.router,   prefix="/api/v1")
app.include_router(calendar_router.router,   prefix="/api/v1")
app.include_router(leaves_router.router,     prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health():
    """Health check — no auth required."""
    return {"status": "ok"}
