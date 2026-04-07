from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import GoogleLoginRequest, LoginRequest, RefreshRequest, TokenResponse
from app.services.auth_service import google_login, login, logout, refresh

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login_route(data: LoginRequest, db: Session = Depends(get_db)):
    return login(str(data.email), db)


@router.post("/refresh", response_model=TokenResponse)
def refresh_route(data: RefreshRequest, db: Session = Depends(get_db)):
    return refresh(data.refresh_token, db)


@router.post("/logout")
def logout_route(data: RefreshRequest, db: Session = Depends(get_db)):
    logout(data.refresh_token, db)
    return {"message": "Logged out"}


@router.get("/me")
def get_me(user=Depends(get_current_user)):
    return user


@router.post("/google-login", response_model=TokenResponse)
def google_login_route(data: GoogleLoginRequest, db: Session = Depends(get_db)):
    return google_login(data.id_token, db)