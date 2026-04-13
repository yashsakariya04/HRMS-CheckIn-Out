"""
app/core/security.py — Token & Password Security Utilities
===========================================================
Provides all cryptographic helpers used for authentication:
  - Creating short-lived access tokens (JWT)
  - Decoding and verifying access tokens
  - Creating long-lived refresh tokens (opaque random strings)
  - Hashing and verifying refresh tokens (stored as SHA-256 hashes)

Non-technical summary:
----------------------
When an employee logs in, they receive two "keys":
  1. Access token  — a short-lived key (15 min) used for every API call.
  2. Refresh token — a long-lived key (1 year) used only to get a new
                     access token when the old one expires.

This file contains the tools to create, read, and verify those keys.
Passwords are NOT used — the system relies entirely on Google OAuth.
"""

import hmac
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings

# Retained as a placeholder in case password-based auth is added later.
pwd_context = None


def create_access_token(data: dict) -> str:
    """
    Create a signed JWT access token.

    The token encodes the given `data` payload (typically {"sub": employee_id})
    and adds standard JWT claims:
      - exp: expiry timestamp (now + ACCESS_TOKEN_EXPIRE_MINUTES)
      - iat: issued-at timestamp
      - type: "access" (so we can reject refresh tokens used as access tokens)

    Args:
        data: Dictionary of claims to embed in the token.
              Must include "sub" (subject = employee UUID as string).

    Returns:
        Signed JWT string to send to the client.
    """
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
    """
    Decode and verify a JWT access token.

    Tries the primary JWT_SECRET_KEY first. If a legacy SECRET_KEY is
    configured, it also tries that key to support tokens issued before
    a key rotation.

    Rejects tokens whose `type` claim is not "access" (e.g. refresh tokens
    accidentally passed as access tokens).

    Args:
        token: Raw JWT string from the Authorization header.

    Returns:
        Decoded payload dict if valid, or None if invalid/expired.
    """
    # Build list of keys to try (primary first, legacy second if configured)
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
            # Reject tokens that are not access tokens (e.g. future token types)
            token_type = payload.get("type")
            if token_type is not None and token_type != "access":
                continue
            return payload
        except JWTError:
            continue  # Try next key

    return None  # All keys failed


def create_refresh_token() -> str:
    """
    Create an opaque refresh token as two UUID segments joined by a dot.

    Format: "<token_id>.<secret>"
      - token_id: stored in the database to look up the token record.
      - secret:   hashed and stored; the raw value is never saved.

    Returns:
        Raw refresh token string (e.g. "uuid1.uuid2").
        Split on "." to get (token_id, secret).
    """
    token_id = str(uuid.uuid4())
    secret = str(uuid.uuid4())
    return f"{token_id}.{secret}"


def hash_token(token: str) -> str:
    """
    Return the SHA-256 hex digest of the given string.

    Used to hash the refresh token secret before storing it in the database.
    We never store the raw secret — only its hash — so even a database
    breach cannot be used to forge tokens.

    Args:
        token: Raw string to hash (the secret part of a refresh token).

    Returns:
        64-character hex string (SHA-256 digest).
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, hashed: str) -> bool:
    """
    Verify that a raw token matches its stored hash.
    Uses hmac.compare_digest to prevent timing attacks.

    Args:
        token:  Raw token string provided by the client.
        hashed: SHA-256 hash stored in the database.

    Returns:
        True if the token matches the hash, False otherwise.
    """
    return hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), hashed)
