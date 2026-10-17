"""Seed a fictitious, already-verified organization for local demos.

The organization and its owner account are clearly fictitious and exist only so
a presenter can sign in and record coordination actions during a rehearsal or
a recorded demo. Never run this against a shared or production database.

Idempotent: re-running it resets the demo password and keeps a single
organization and a single owner account.

Usage, from ``backend/``::

    uv run python -m scripts.seed_demo_institution
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import async_session_factory
from app.modules.institutions.infrastructure.models import (
    InstitutionModel,
    InstitutionUserModel,
)
from app.modules.institutions.infrastructure.security import password_hasher

DEMO_ORGANIZATION_NAME = "Brigada Demo FirstSpot (ficticia)"
DEMO_REGISTRATION_CODE = "FSP-DEMO000001"
# example.com is reserved for documentation (RFC 2606) and accepted by the API's
# email validator; special-use TLDs such as .test are rejected at login.
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "FirstSpotDemo2026!"
DEMO_DISPLAY_NAME = "Coordinación Demo"


async def seed() -> None:
    async with async_session_factory() as session:
        organization = await session.scalar(
            select(InstitutionModel).where(
                InstitutionModel.registration_code == DEMO_REGISTRATION_CODE
            )
        )
        if organization is None:
            organization = InstitutionModel(
                name=DEMO_ORGANIZATION_NAME,
                country="El Salvador",
                sector="Protección civil",
                contact_email=DEMO_EMAIL,
                registration_code=DEMO_REGISTRATION_CODE,
            )
            session.add(organization)
        organization.verification_status = "verified"
        organization.verified_at = organization.verified_at or datetime.now(timezone.utc)
        organization.reviewer_note = "Fictitious organization for local demos only."
        await session.flush()

        # Look the owner up by organization, so a changed demo email updates the
        # same account instead of leaving an orphan behind.
        user = await session.scalar(
            select(InstitutionUserModel).where(
                InstitutionUserModel.institution_id == organization.id,
                InstitutionUserModel.role == "owner",
            )
        )
        if user is None:
            user = InstitutionUserModel(
                institution_id=organization.id,
                display_name=DEMO_DISPLAY_NAME,
                email=DEMO_EMAIL,
                role="owner",
            )
            session.add(user)
        user.email = DEMO_EMAIL
        organization.contact_email = DEMO_EMAIL
        user.password_hash = password_hasher.hash(DEMO_PASSWORD)
        user.is_active = True
        await session.commit()

    print(f"Demo organization ready: {DEMO_ORGANIZATION_NAME} (verified)")
    print(f"Sign in with: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
