"""Backfill the cached place-to-census attachment and exposure estimates.

This is the backfill path for rows that existed before migration 0004. Newly
synced places resolve on insert, so this script only has to be run once after
the migration, and again whenever the census corpus is re-ingested.

Both passes are idempotent, so re-running is safe and a second run reports zero
changes. Run from the ``backend/`` directory with PostGIS up:

    uv run python -m scripts.attach_place_census

or ``just census-attach``.
"""

import argparse
import asyncio

from sqlalchemy import text

from app.core.database import async_session_factory
from app.modules.census.domain.exposure import DEFAULT_EXPOSURE_RADIUS_METERS
from app.modules.places.infrastructure.census_attachment import (
    PlaceCensusAttachmentRepository,
)

_SAMPLE_ESTIMATES = text(
    """
    SELECT p.name,
           p.zone_name,
           p.category,
           p.estimated_exposed_population,
           p.estimated_exposed_older_adults,
           p.estimated_exposed_young_children,
           p.estimated_exposed_persons_with_disability,
           u.district_code,
           u.dug_class
    FROM vulnerable_places p
    LEFT JOIN census_population_unit u ON u.id = p.census_unit_id
    WHERE p.estimated_exposed_population IS NOT NULL
    ORDER BY p.estimated_exposed_population DESC
    LIMIT CAST(:sample AS integer)
    """
)


async def run(arguments: argparse.Namespace) -> int:
    """Attach places to census units, refresh estimates, and report a sample."""
    async with async_session_factory() as session:
        repository = PlaceCensusAttachmentRepository(session)

        attachment = await repository.attach_places_to_census_units(
            zone_name=arguments.zone
        )
        print(attachment)

        exposure = await repository.refresh_exposure_estimates(
            radius_meters=arguments.radius_meters,
            zone_name=arguments.zone,
        )
        print(exposure)

        if arguments.sample:
            rows = (
                await session.execute(_SAMPLE_ESTIMATES, {"sample": arguments.sample})
            ).all()
            print(
                f"\nHighest estimated exposed resident population at "
                f"{arguments.radius_meters} m (estimates, not counts of people "
                f"present):"
            )
            for row in rows:
                print(
                    f"  {row.name[:44]:<44} {row.zone_name:<14} "
                    f"pop~{row.estimated_exposed_population:>7,} "
                    f"65+~{_format(row.estimated_exposed_older_adults):>6} "
                    f"u5~{_format(row.estimated_exposed_young_children):>6} "
                    f"disab~{_format(row.estimated_exposed_persons_with_disability):>6} "
                    f"[{row.district_code} {str(row.dug_class)[:28]}]"
                )
    return 0


def _format(value: int | None) -> str:
    """Render a withheld figure as a dash rather than as a zero."""
    return "withheld" if value is None else f"{value:,}"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        prog="attach_place_census",
        description=(
            "Cache each vulnerable place's census unit and its areal-weighted "
            "estimate of exposed resident population. Idempotent."
        ),
        epilog=(
            "Run from the backend/ directory with PostGIS up: "
            "uv run python -m scripts.attach_place_census"
        ),
    )
    parser.add_argument(
        "--radius-meters",
        type=int,
        default=DEFAULT_EXPOSURE_RADIUS_METERS,
        help="Radius for the cached estimate (default: %(default)s)",
    )
    parser.add_argument(
        "--zone",
        default=None,
        help="Restrict to one zone_name (default: every place)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=10,
        help="Print this many of the highest estimates (default: %(default)s)",
    )
    return parser


def main() -> int:
    """Entry point."""
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
