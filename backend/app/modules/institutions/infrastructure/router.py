"""Public organization onboarding, manual verification, and institution membership."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Annotated, Literal
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db_session
from app.modules.institutions.infrastructure.models import (
    InstitutionInviteModel,
    InstitutionModel,
    InstitutionUserModel,
)
from app.modules.institutions.infrastructure.security import (
    ensure_jwt_secret,
    get_current_institution_user,
    issue_access_token,
    password_hasher,
    require_institution_owner,
)

router = APIRouter(prefix="/institutions", tags=["institutions"])


class InstitutionRegistrationRequest(BaseModel):
    """Request an organization listing; the generated code only tracks review."""

    name: str = Field(min_length=2, max_length=160)
    country: str = Field(min_length=2, max_length=80)
    sector: str = Field(min_length=2, max_length=80)
    contact_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class InstitutionRegistrationRead(BaseModel):
    registration_code: str
    verification_status: Literal["pending"]
    message: str


class InstitutionPublicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str
    sector: str
    registration_code: str
    verification_status: Literal["pending", "verified", "rejected"]
    created_at: datetime
    verified_at: datetime | None


class InstitutionAccountRead(BaseModel):
    id: uuid.UUID
    display_name: str
    email: EmailStr
    role: Literal["owner", "member"]
    institution: InstitutionPublicRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    account: InstitutionAccountRead


class VerificationDecision(BaseModel):
    registration_code: str = Field(min_length=8, max_length=24)
    decision: Literal["verify", "reject"]
    reviewer_note: str | None = Field(default=None, max_length=500)


class InviteCreateRead(BaseModel):
    invite_code: str
    expires_at: datetime
    message: str


class InstitutionJoinRequest(BaseModel):
    invite_code: str = Field(min_length=20, max_length=100)
    display_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _account_read(user: InstitutionUserModel) -> InstitutionAccountRead:
    return InstitutionAccountRead(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        role=user.role,
        institution=InstitutionPublicRead.model_validate(user.institution),
    )


@router.post(
    "/register",
    response_model=InstitutionRegistrationRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="registerInstitution",
    summary="Submit an institution for independent verification",
)
async def register_institution(
    payload: InstitutionRegistrationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> InstitutionRegistrationRead:
    """Create a pending organization and its owner account."""
    email = _normalize_email(str(payload.email))
    existing = await session.scalar(
        select(InstitutionUserModel.id).where(InstitutionUserModel.email == email)
    )
    if existing:
        raise HTTPException(status_code=409, detail="An account already uses this email.")

    organization = InstitutionModel(
        name=payload.name.strip(),
        country=payload.country.strip(),
        sector=payload.sector.strip(),
        contact_email=email,
        registration_code=f"FSP-{secrets.token_hex(6).upper()}",
        verification_status="pending",
    )
    owner = InstitutionUserModel(
        institution=organization,
        display_name=payload.contact_name.strip(),
        email=email,
        password_hash=password_hasher.hash(payload.password),
        role="owner",
    )
    session.add_all([organization, owner])
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="The account could not be registered.") from exc

    return InstitutionRegistrationRead(
        registration_code=organization.registration_code,
        verification_status="pending",
        message=(
            "Request submitted for review. This code tracks the request; it does not prove the organization's identity."
        ),
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    operation_id="loginInstitutionUser",
    summary="Sign in as an individual institutional account",
)
async def login_institution_user(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    """Authenticate with Argon2id password hash and issue a short-lived token."""
    email = _normalize_email(str(payload.email))
    stmt = (
        select(InstitutionUserModel)
        .where(InstitutionUserModel.email == email)
        .options(selectinload(InstitutionUserModel.institution))
    )
    user = (await session.scalars(stmt)).first()
    if user is None or not password_hasher.verify(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=401, detail="This account is inactive.")

    access_token, expires_in = issue_access_token(user)
    return LoginResponse(
        access_token=access_token,
        expires_in=expires_in,
        account=_account_read(user),
    )


@router.get(
    "/me",
    response_model=InstitutionAccountRead,
    operation_id="getInstitutionAccount",
    summary="Get the signed-in institution account",
)
async def get_institution_account(
    user: Annotated[InstitutionUserModel, Depends(get_current_institution_user)],
) -> InstitutionAccountRead:
    return _account_read(user)


@router.post(
    "/verification",
    response_model=InstitutionPublicRead,
    operation_id="reviewInstitutionRegistration",
    summary="Verify or reject an organization after independent review",
)
async def review_institution_registration(
    payload: VerificationDecision,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    admin_key: Annotated[str | None, Header(alias="X-Platform-Admin-Key")] = None,
) -> InstitutionPublicRead:
    """Moderate a registration; never treat its public reference code as proof."""
    expected_key = settings.platform_admin_key
    if len(expected_key) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Institution review is not configured: set PLATFORM_ADMIN_KEY to at least 32 characters.",
        )
    if admin_key is None or not hmac.compare_digest(admin_key, expected_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

    organization = await session.scalar(
        select(InstitutionModel).where(
            InstitutionModel.registration_code == payload.registration_code.strip().upper()
        )
    )
    if organization is None:
        raise HTTPException(status_code=404, detail="Registration request not found.")
    organization.verification_status = "verified" if payload.decision == "verify" else "rejected"
    organization.verified_at = datetime.now(timezone.utc) if payload.decision == "verify" else None
    organization.reviewer_note = payload.reviewer_note
    await session.commit()
    await session.refresh(organization)
    return InstitutionPublicRead.model_validate(organization)


@router.post(
    "/invites",
    response_model=InviteCreateRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createInstitutionInvite",
    summary="Create a one-time invitation for a colleague",
)
async def create_institution_invite(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    owner: Annotated[InstitutionUserModel, Depends(require_institution_owner)],
) -> InviteCreateRead:
    """Issue a high-entropy invitation, storing only its SHA-256 digest."""
    invite_code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=min(max(settings.institution_invite_hours, 1), 168)
    )
    invite = InstitutionInviteModel(
        institution_id=owner.institution_id,
        created_by_user_id=owner.id,
        code_hash=hashlib.sha256(invite_code.encode()).hexdigest(),
        expires_at=expires_at,
    )
    session.add(invite)
    await session.commit()
    return InviteCreateRead(
        invite_code=invite_code,
        expires_at=expires_at,
        message="Share this one-time link securely. The code is shown only once.",
    )


@router.post(
    "/join",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="joinInstitution",
    summary="Join a verified institution using a one-time invitation",
)
async def join_institution(
    payload: InstitutionJoinRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    """Redeem a single-use invite and create an individual member account."""
    ensure_jwt_secret()
    email = _normalize_email(str(payload.email))
    existing = await session.scalar(
        select(InstitutionUserModel.id).where(InstitutionUserModel.email == email)
    )
    if existing:
        raise HTTPException(status_code=409, detail="An account already uses this email.")

    code_hash = hashlib.sha256(payload.invite_code.encode()).hexdigest()
    invite = await session.scalar(
        select(InstitutionInviteModel)
        .where(
            InstitutionInviteModel.code_hash == code_hash,
            InstitutionInviteModel.redeemed_at.is_(None),
            InstitutionInviteModel.expires_at > datetime.now(timezone.utc),
        )
        .with_for_update()
    )
    if invite is None:
        raise HTTPException(status_code=400, detail="Invitation is invalid, expired, or already used.")

    organization = await session.scalar(
        select(InstitutionModel)
        .where(InstitutionModel.id == invite.institution_id)
        .options(selectinload(InstitutionModel.users))
    )
    if organization is None or organization.verification_status != "verified":
        raise HTTPException(status_code=403, detail="The inviting organization is not verified.")

    user = InstitutionUserModel(
        institution_id=organization.id,
        display_name=payload.display_name.strip(),
        email=email,
        password_hash=password_hasher.hash(payload.password),
        role="member",
    )
    invite.redeemed_at = datetime.now(timezone.utc)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="The account could not be created.") from exc

    user.institution = organization
    access_token, expires_in = issue_access_token(user)
    return LoginResponse(
        access_token=access_token,
        expires_in=expires_in,
        account=_account_read(user),
    )
