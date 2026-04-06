import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ACCESS TOKEN (JWT)
def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),   # issued at
        "type": "access"                     #  important
    })

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


# DECODE TOKEN
def decode_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        # extra validation
        if payload.get("type") != "access":
            return None

        return payload

    except JWTError:
        return None


#  REFRESH TOKEN
def create_refresh_token():
    token_id = str(uuid.uuid4())
    secret = str(uuid.uuid4())

    return f"{token_id}.{secret}"


#  HASH TOKEN
def hash_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, hashed: str):
    return hashlib.sha256(token.encode()).hexdigest() == hashed