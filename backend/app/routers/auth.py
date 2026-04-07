from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest
from backend.app.services.auth_service import login, refresh, logout
from backend.app.dependencies.database import get_db
from backend.app.dependencies.auth import get_current_user
from backend.app.schemas.auth import GoogleLoginRequest
from backend.app.services.auth_service import google_login

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=TokenResponse)
async def login_route(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login(data.email, db)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_route(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await refresh(data.refresh_token, db)

@router.post("/logout")
async def logout_route(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await logout(data.refresh_token, db)
    return {"message": "Logged out"}

@router.get("/me")
async def get_me(user = Depends(get_current_user)):
    return user

@router.post("/google-login", response_model=TokenResponse)
async def google_login_route(data: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    return await google_login(data.id_token, db)