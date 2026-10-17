"""Password hashing, signed access tokens, and verified-member dependencies."""

from datetime import datetime, timedelta, timezone
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db_session
from app.modules.institutions.infrastructure.models import InstitutionUserModel

password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def ensure_jwt_secret() -> str:
    """Refuse token operations unless deployment supplies a nontrivial secret."""
    if len(settings.jwt_secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Institutional access is not configured: set JWT_SECRET to at least 32 characters.",
        )
    return settings.jwt_secret


def issue_access_token(user: InstitutionUserModel) -> tuple[str, int]:
    """Create a signed, short-lived bearer token containing only the user UUID."""
    secret = ensure_jwt_secret()
    expires_in = max(5, settings.access_token_minutes) * 60
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
            "iss": "firstsopot",
        },
        secret,
        algorithm="HS256",
    )
    return token, expires_in


async def get_current_institution_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstitutionUserModel:
    """Resolve the authenticated individual and eagerly load its organization."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Institutional sign-in required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = ensure_jwt_secret()
    try:
        claims = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            issuer="firstsopot",
            options={"require": ["exp", "sub", "iat", "iss"]},
        )
        user_id = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired institutional session.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    stmt = (
        select(InstitutionUserModel)
        .where(InstitutionUserModel.id == user_id)
        .options(selectinload(InstitutionUserModel.institution))
    )
    user = (await session.scalars(stmt)).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Institutional account is unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_verified_institution(
    user: Annotated[InstitutionUserModel, Depends(get_current_institution_user)],
) -> InstitutionUserModel:
    """Allow official public activity only for an independently verified organization."""
    if user.institution.verification_status != "verified":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your organization must be verified before publishing institutional activity.",
        )
    return user


async def require_institution_owner(
    user: Annotated[InstitutionUserModel, Depends(require_verified_institution)],
) -> InstitutionUserModel:
    """Restrict invitation issuance to an organization's verified owner."""
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the verified organization owner can issue invitations.",
        )
    return user
