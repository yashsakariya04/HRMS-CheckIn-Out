# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.employee import Employee
from app.services import auth_service

# auto_error=False means we handle the missing token ourselves
# This gives us 401 instead of 403 when token is missing
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Employee:
    """
    Read JWT from Authorization header.
    Returns 401 if token is missing or invalid.
    """
    # Token is missing entirely
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = auth_service.decode_access_token(credentials.credentials)
    employee_id = payload.get("sub")

    if not employee_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    return auth_service.get_employee_by_id(db, employee_id)


def require_admin(
    current_user: Employee = Depends(get_current_user),
) -> Employee:
    """Raises 403 if user is not admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user