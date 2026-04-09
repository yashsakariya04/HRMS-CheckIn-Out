import uuid
import hashlib
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

from app.core.config import settings

pwd_context = None  # retained for potential future password flows


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    })
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict | None:
    keys: list[str] = [settings.JWT_SECRET_KEY]
    if settings.SECRET_KEY and settings.SECRET_KEY not in keys:
        keys.append(settings.SECRET_KEY)
    for key in keys:
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[settings.JWT_ALGORITHM],
            )
            token_type = payload.get("type")
            if token_type is not None and token_type != "access":
                continue
            return payload
        except JWTError:
            continue
    return None


def create_refresh_token() -> str:
    token_id = str(uuid.uuid4())
    secret = str(uuid.uuid4())
    return f"{token_id}.{secret}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, hashed: str) -> bool:
    return hashlib.sha256(token.encode()).hexdigest() == hashed
