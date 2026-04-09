# import uuid
# from datetime import date, datetime, timedelta, timezone

# from fastapi import HTTPException, status
# from google.auth.transport import requests
# from google.oauth2 import id_token as google_id_token
# from sqlalchemy import and_
# from sqlalchemy.orm import Session

# from app.config import settings
# from app.core.security import (
#     create_access_token,
#     create_refresh_token,
#     decode_token,
#     hash_token,
#     verify_token,
# )
# from app.models.employee import Employee
# from app.models.refresh_token import RefreshToken


# def decode_access_token(token: str) -> dict:
#     payload = decode_token(token)
#     if not payload:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired token.",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     return payload


# def get_employee_by_id(db: Session, employee_id: str | uuid.UUID) -> Employee:
#     try:
#         uid = uuid.UUID(str(employee_id))
#     except ValueError as exc:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token subject.",
#         ) from exc
#     user = db.query(Employee).filter(Employee.id == uid).first()
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="User not found.",
#         )
#     return user


# def login(email: str, db: Session) -> dict:
#     user = db.query(Employee).filter(Employee.email == email).first()

#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")

#     if not user.is_active:
#         raise HTTPException(status_code=403, detail="User is inactive")

#     if user.joined_on is None:
#         user.joined_on = date.today()

#     user.last_login_at = datetime.now(timezone.utc)

#     access_token_str = create_access_token({"sub": str(user.id)})
#     refresh_token_str = create_refresh_token()
#     token_id, secret = refresh_token_str.split(".", 1)

#     db_token = RefreshToken(
#         employee_id=user.id,
#         token_id=token_id,
#         token_hash=hash_token(secret),
#         expires_at=datetime.now(timezone.utc)
#         + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
#     )
#     db.add(db_token)
#     db.commit()

#     return {
#         "access_token": access_token_str,
#         "refresh_token": refresh_token_str,
#         "token_type": "bearer",
#     }


# def refresh(refresh_token_value: str, db: Session) -> dict:
#     try:
#         token_id, secret = refresh_token_value.split(".", 1)
#     except ValueError as exc:
#         raise HTTPException(
#             status_code=400, detail="Invalid token format"
#         ) from exc

#     db_token = (
#         db.query(RefreshToken)
#         .filter(
#             and_(
#                 RefreshToken.token_id == token_id,
#                 RefreshToken.is_revoked == False,  # noqa: E712
#             )
#         )
#         .first()
#     )

#     if not db_token:
#         raise HTTPException(status_code=401, detail="Invalid token")

#     if db_token.expires_at < datetime.now(timezone.utc):
#         raise HTTPException(status_code=401, detail="Token expired")

#     if not verify_token(secret, db_token.token_hash):
#         raise HTTPException(status_code=401, detail="Invalid token")

#     access_token_str = create_access_token({"sub": str(db_token.employee_id)})

#     return {
#         "access_token": access_token_str,
#         "refresh_token": refresh_token_value,
#         "token_type": "bearer",
#     }


# def logout(refresh_token_value: str, db: Session) -> None:
#     try:
#         token_id, _ = refresh_token_value.split(".", 1)
#     except ValueError as exc:
#         raise HTTPException(
#             status_code=400, detail="Invalid token format"
#         ) from exc

#     db_token = (
#         db.query(RefreshToken)
#         .filter(
#             and_(
#                 RefreshToken.token_id == token_id,
#                 RefreshToken.is_revoked == False,  # noqa: E712
#             )
#         )
#         .first()
#     )

#     if not db_token:
#         raise HTTPException(status_code=401, detail="Invalid token")

#     db_token.is_revoked = True
#     db.commit()


# def google_login(id_token_str: str, db: Session) -> dict:
#     try:
#         idinfo = google_id_token.verify_oauth2_token(
#             id_token_str,
#             requests.Request(),
#             settings.GOOGLE_CLIENT_ID,
#         )
#     except Exception:
#         raise HTTPException(status_code=401, detail="Invalid Google token")

#     email = idinfo.get("email")
#     name = idinfo.get("name")
#     picture = idinfo.get("picture")

#     user = db.query(Employee).filter(Employee.email == email).first()

#     if not user:
#         raise HTTPException(
#             status_code=403, detail="Access denied. Contact admin"
#         )

#     if not user.is_active:
#         raise HTTPException(status_code=403, detail="User is inactive")

#     if not user.full_name:
#         user.full_name = name
#     if not user.photo_url:
#         user.photo_url = picture

#     if user.joined_on is None:
#         user.joined_on = date.today()

#     user.last_login_at = datetime.now(timezone.utc)

#     access_token_str = create_access_token({"sub": str(user.id)})
#     refresh_token_str = create_refresh_token()
#     token_id, secret = refresh_token_str.split(".", 1)

#     db_token = RefreshToken(
#         employee_id=user.id,
#         token_id=token_id,
#         token_hash=hash_token(secret),
#         expires_at=datetime.now(timezone.utc)
#         + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
#     )
#     db.add(db_token)
#     db.commit()

#     return {
#         "access_token": access_token_str,
#         "refresh_token": refresh_token_str,
#         "token_type": "bearer",
#     }


from datetime import datetime, timedelta , timezone , date
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.employee import Employee
from app.models.refresh_token import RefreshToken
from app.core.security import create_access_token, create_refresh_token, hash_token, verify_token
from app.core.config import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from fastapi import HTTPException

async def login(email: str, db: AsyncSession):
    result = await db.execute(select(Employee).where(Employee.email == email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    
    # First login check
    if user.joined_on is None:
        user.joined_on = date.today()

    # Always update last login
    user.last_login_at = datetime.now(timezone.utc)

    await db.commit()

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token()

    token_id, secret = refresh_token.split(".")

    db_token = RefreshToken(
        employee_id=user.id,
        token_id=token_id,
        token_hash=hash_token(secret),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )

    db.add(db_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

async def refresh(refresh_token: str, db: AsyncSession):
    try:
        token_id, secret = refresh_token.split(".")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token format")

    result = await db.execute(select(RefreshToken).where(
        and_(
            RefreshToken.token_id == token_id,
            RefreshToken.is_revoked == False
        )
    ))
    db_token = result.scalars().first()

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    if db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")

    if not verify_token(secret, db_token.token_hash):
        raise HTTPException(status_code=401, detail="Invalid token")

    access_token = create_access_token({"sub": str(db_token.employee_id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }

async def logout(refresh_token: str, db: AsyncSession):
    try:
        token_id, _ = refresh_token.split(".")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token format")

    result = await db.execute(select(RefreshToken).where(
        and_(
            RefreshToken.token_id == token_id,
            RefreshToken.is_revoked == False
        )
    ))
    db_token = result.scalars().first()

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_token.is_revoked = True
    await db.commit()
    


async def google_login(id_token_str: str, db: AsyncSession):
    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = idinfo.get("email")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    result = await db.execute(
        select(Employee).where(Employee.email == email)
    )
    user = result.scalars().first()

    # If NOT exists → reject
    if not user:
        raise HTTPException(status_code=403, detail="Access denied. Contact admin")

    if not user.is_active:   # ADD HERE
        raise HTTPException(status_code=403, detail="User is inactive")

    # Auto-fill only if empty
    if not user.full_name:
        user.full_name = name

    if not user.photo_url:
        user.photo_url = picture

    if user.joined_on is None:
        user.joined_on = date.today()

    #  Always update last login
    user.last_login_at = datetime.now(timezone.utc)

    await db.commit()

    # SAME TOKEN LOGIC (reuse)
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token()

    token_id, secret = refresh_token.split(".")

    db_token = RefreshToken(
        employee_id=user.id,
        token_id=token_id,
        token_hash=hash_token(secret),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )

    db.add(db_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }    