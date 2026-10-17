"""Seed a fictitious multi-agency coordination drill for local demos.

It creates a second fictitious, verified organization and writes a short,
attributed coordination log ("Simulacro: ...") on the place the guided tour
shows, so the recorded demo can show two organizations coordinating on one
record. Never run this against a shared or production database.

The target place is resolved exactly as the tour resolves it, through the same
API endpoint the frontend reads (``GET /api/v1/places?zone_name=...``): the
first place of the Sonsonate queue with a real name and a census estimate. The
API must therefore be running.

Idempotent: a re-run that finds the drill already on the tour's place changes
nothing. The coordination log is append-only by design (a database trigger
rejects UPDATE and DELETE), so this script never edits or deletes log entries:
if a different or partial drill is already there, it stops and says so.
``--reset`` removes only the second organization and its owner account, and
only while no log entry references them; with the drill in place it refuses.
It never touches the organization from ``seed_demo_institution``.

Usage, from ``backend/``::

    uv run python -m scripts.seed_demo_coordination
    uv run python -m scripts.seed_demo_coordination --reset
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
# Registers census_population_unit, which vulnerable_places references by foreign key.
from app.modules.census.infrastructure import models as _census_models  # noqa: F401
from app.modules.institutions.infrastructure.models import (
    InstitutionModel,
    InstitutionUserModel,
)
from app.modules.institutions.infrastructure.security import password_hasher
from app.modules.places.infrastructure.models import (
    PlaceActivityModel,
    VulnerablePlaceModel,
)
from scripts import seed_demo_institution as first_org

SECOND_ORGANIZATION_NAME = "Cuerpo de Socorro Demo (ficticio)"
SECOND_REGISTRATION_CODE = "FSP-DEMO000002"
SECOND_EMAIL = "socorro.demo@example.com"
SECOND_PASSWORD = "demo1234"
SECOND_DISPLAY_NAME = "Central Socorro Demo"

DRILL_PREFIX = "Simulacro:"
DEFAULT_API_URL = "http://127.0.0.1:8000"
# The tour's demo zone (DEMO_ZONE_KEY in frontend/src/modules/guided-tour/tourSteps.ts).
DEMO_ZONE_KEY = "sonsonate"

# Same shapes as frontend/src/utils/placeName.ts.
SYNTHESISED_NAME = re.compile(r"^unnamed\s+.+\s+\(#\d+\)$", re.IGNORECASE)
OSM_ID_FRAGMENT = re.compile(r"\(#\d+\)")

# (minutes before the latest entry, organization, activity_type, note).
# "first" is the Brigada from seed_demo_institution; "second" is created here.
DRILL_LOG: tuple[tuple[int, str, str, str], ...] = (
    (
        24, "first", "reported",
        "Simulacro: grietas en muros del aula principal y parte del techo caído. "
        "46 personas en el edificio: 38 niñas y niños y 8 adultos; sin heridos graves.",
    ),
    (
        19, "second", "en_route",
        "Simulacro: sale la unidad de rescate R-3 con 4 socorristas. Llegada estimada: 12 min.",
    ),
    (
        13, "first", "needs_support",
        "Simulacro: solicitamos lonas y agua para resguardar a 38 menores en el patio "
        "mientras se revisa la estructura.",
    ),
    (
        9, "second", "resource_available",
        "Simulacro: enviamos 6 lonas y 200 L de agua en un segundo vehículo; sale en 10 min.",
    ),
    (
        0, "second", "on_scene",
        "Simulacro: R-3 en el lugar. Iniciamos evaluación estructural y evacuación ordenada al patio.",
    ),
)

# What the app's own write path sets for each type (activity_router._write_activity).
IN_PROGRESS_TYPES = {"en_route", "on_scene", "needs_support"}


def _has_real_name(place: dict[str, Any]) -> bool:
    """Port of describePlaceName(place, "es").isUnnamed == False."""
    tags = place.get("osm_tags") or {}
    tagged = tags.get("name:es") if isinstance(tags, dict) else None
    candidates = [tagged.strip() if isinstance(tagged, str) else None, (place.get("name") or "").strip()]
    for candidate in candidates:
        if not candidate:
            continue
        if SYNTHESISED_NAME.match(candidate):
            return False
        if not OSM_ID_FRAGMENT.search(candidate):
            return True
        return bool(re.sub(r"\s{2,}", " ", OSM_ID_FRAGMENT.sub("", candidate)).strip())
    return False


def _has_estimate(place: dict[str, Any]) -> bool:
    """Port of exposedPopulationState(place).kind === "estimate"."""
    exposure = place.get("population_exposure") or {}
    value = exposure.get("estimated_exposed_population")
    return isinstance(value, (int, float)) and math.isfinite(value)


def _get_json(url: str) -> Any:
    with urlopen(url, timeout=30) as response:  # noqa: S310 - local API only
        return json.load(response)


def resolve_tour_place(api_url: str) -> dict[str, Any]:
    """Apply the tour's pickDemoPlace rule to the queue the frontend loads."""
    zones = _get_json(f"{api_url}/api/v1/zones")
    zone = next((z for z in zones if z.get("key") == DEMO_ZONE_KEY), None)
    if zone is None:
        raise SystemExit(f"The API has no '{DEMO_ZONE_KEY}' zone; the tour cannot pick a place.")
    places = _get_json(f"{api_url}/api/v1/places?{urlencode({'zone_name': zone['name']})}")
    if not places:
        raise SystemExit(f"The API returned no places for {zone['name']}.")
    picked = next((p for p in places if _has_real_name(p) and _has_estimate(p)), places[0])
    return picked


async def _ensure_second_organization(session: AsyncSession) -> InstitutionUserModel:
    organization = await session.scalar(
        select(InstitutionModel).where(InstitutionModel.registration_code == SECOND_REGISTRATION_CODE)
    )
    if organization is None:
        organization = InstitutionModel(
            name=SECOND_ORGANIZATION_NAME,
            country="El Salvador",
            sector="Bomberos",
            contact_email=SECOND_EMAIL,
            registration_code=SECOND_REGISTRATION_CODE,
        )
        session.add(organization)
    organization.name = SECOND_ORGANIZATION_NAME
    organization.verification_status = "verified"
    organization.verified_at = organization.verified_at or datetime.now(timezone.utc)
    organization.reviewer_note = "Fictitious organization for local demos only."
    await session.flush()

    user = await session.scalar(
        select(InstitutionUserModel).where(
            InstitutionUserModel.institution_id == organization.id,
            InstitutionUserModel.role == "owner",
        )
    )
    if user is None:
        user = InstitutionUserModel(
            institution_id=organization.id,
            display_name=SECOND_DISPLAY_NAME,
            email=SECOND_EMAIL,
            role="owner",
        )
        session.add(user)
    user.display_name = SECOND_DISPLAY_NAME
    user.email = SECOND_EMAIL
    user.password_hash = password_hasher.hash(SECOND_PASSWORD)
    user.is_active = True
    await session.flush()
    return user


async def _first_owner(session: AsyncSession) -> InstitutionUserModel:
    user = await session.scalar(
        select(InstitutionUserModel)
        .join(InstitutionModel, InstitutionModel.id == InstitutionUserModel.institution_id)
        .where(
            InstitutionModel.registration_code == first_org.DEMO_REGISTRATION_CODE,
            InstitutionUserModel.role == "owner",
        )
    )
    if user is None:
        raise SystemExit("The first demo organization is missing; seed_demo_institution did not run.")
    return user


async def _demo_org_ids(session: AsyncSession) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(InstitutionModel.id).where(
            InstitutionModel.registration_code.in_(
                [first_org.DEMO_REGISTRATION_CODE, SECOND_REGISTRATION_CODE]
            )
        )
    )
    return list(rows)


async def _drill_entries(session: AsyncSession) -> list[tuple[uuid.UUID, str]]:
    """Drill entries already written by the demo organizations, as (place_id, note)."""
    org_ids = await _demo_org_ids(session)
    if not org_ids:
        return []
    rows = await session.execute(
        select(PlaceActivityModel.place_id, PlaceActivityModel.notes).where(
            PlaceActivityModel.organization_id.in_(org_ids),
            PlaceActivityModel.notes.startswith(DRILL_PREFIX),
        )
    )
    return [(place_id, notes) for place_id, notes in rows]


APPEND_ONLY_NOTE = (
    "place_activities is an append-only audit log (trigger place_activities_immutable): "
    "this script never edits or deletes its entries. To start from a clean log, recreate "
    "the local database."
)


async def seed(api_url: str) -> None:
    await first_org.seed()
    picked = resolve_tour_place(api_url)
    place_id = uuid.UUID(picked["id"])

    async with async_session_factory() as session:
        place = await session.get(VulnerablePlaceModel, place_id)
        if place is None:
            raise SystemExit(f"Place {place_id} from the API is not in this database.")
        if place.attention_status == "attended":
            raise SystemExit("The tour's place is 'attended'; refusing to seed (it would change the pick).")

        first = await _first_owner(session)
        second = await _ensure_second_organization(session)

        existing = await _drill_entries(session)
        expected = sorted(note for *_, note in DRILL_LOG)
        if sorted(note for pid, note in existing if pid == place_id) == expected and all(
            pid == place_id for pid, _ in existing
        ):
            await session.commit()
            print(f"Drill already seeded on: {picked['name']} ({place_id}); nothing to change.")
            return
        if existing:
            # A changed pick or a partial drill: never stack a second copy, never delete.
            raise SystemExit(
                f"A different or partial drill is already in the log ({len(existing)} entries). "
                + APPEND_ONLY_NOTE
            )
        authors = {"first": first, "second": second}

        latest = datetime.now(timezone.utc) - timedelta(minutes=2)
        for minutes_before, org_key, activity_type, note in DRILL_LOG:
            assert note.startswith(DRILL_PREFIX)
            author = authors[org_key]
            status = "in_progress" if activity_type in IN_PROGRESS_TYPES else None
            session.add(
                PlaceActivityModel(
                    place_id=place_id,
                    organization_id=author.institution_id,
                    user_id=author.id,
                    activity_type=activity_type,
                    attention_status=status,
                    notes=note,
                    created_at=latest - timedelta(minutes=minutes_before),
                )
            )
        # The app sets in_progress for en_route/on_scene/needs_support; it never
        # changes the score (only "attended" does), so the tour's pick holds.
        place.attention_status = "in_progress"
        await session.commit()

    print(f"Demo organization ready: {SECOND_ORGANIZATION_NAME} (verified)")
    print(f"Seeded {len(DRILL_LOG)} drill entries on: {picked['name']} ({place_id})")


async def reset() -> None:
    """Remove the second organization and its owner, only while nothing references them."""
    async with async_session_factory() as session:
        existing = await _drill_entries(session)
        if existing:
            places = len({place_id for place_id, _ in existing})
            raise SystemExit(
                f"Not reset: {len(existing)} drill entries on {places} place(s) stay. " + APPEND_ONLY_NOTE
            )
        organization = await session.scalar(
            select(InstitutionModel).where(InstitutionModel.registration_code == SECOND_REGISTRATION_CODE)
        )
        if organization is None:
            print("Nothing to reset.")
            return
        referenced = await session.scalar(
            select(func.count())
            .select_from(PlaceActivityModel)
            .where(PlaceActivityModel.organization_id == organization.id)
        )
        if referenced:
            raise SystemExit(f"Not reset: {SECOND_ORGANIZATION_NAME} has {referenced} log entries.")
        await session.execute(
            delete(InstitutionUserModel).where(InstitutionUserModel.institution_id == organization.id)
        )
        await session.delete(organization)
        await session.commit()
    print(f"Removed {SECOND_ORGANIZATION_NAME} and its owner account.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reset", action="store_true", help="remove the second organization when nothing references it")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="running API (default: %(default)s)")
    args = parser.parse_args()
    asyncio.run(reset() if args.reset else seed(args.api_url.rstrip("/")))


if __name__ == "__main__":
    main()
