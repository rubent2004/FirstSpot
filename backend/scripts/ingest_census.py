"""Load ``data/census/raw/`` into PostGIS, enforcing every verified data defect.

Idempotent: every writer upserts on a natural key, so re-running converges instead
of duplicating. The run fails loudly rather than storing a corpus that drifted:
per-layer unit counts are asserted, and the national population must reconcile as
5,922,921 georeferenced + 107,055 unlocated = 6,029,976.

Usage
-----
Run it from the ``backend/`` directory, with PostGIS up and migrations applied
(``just db-up`` from the repository root does both)::

    # Full ingestion: hierarchy, DEGURBA units, indicators and segments.
    uv run python -m scripts.ingest_census

    # Skip the 10,290 segment polygons (the slowest step, context only).
    uv run python -m scripts.ingest_census --skip-segments

    # Ingest from a different corpus directory.
    uv run python -m scripts.ingest_census --raw-dir /tmp/census-check

    # Validate the corpus and the reconciliation without writing.
    uv run python -m scripts.ingest_census --dry-run

Source: VII Censo de Poblacion y VI de Vivienda 2024, ONEC/BCR.
Published figures derived from it must be attributed as "BCR/ONEC, CPV 2024".
Derived cells holding fewer than 3 statistical units are suppressed before
storage, per the Ley Especial de Estadistica y Censos (D.L. 904).
"""

import argparse
import asyncio
from pathlib import Path
import sys
import time

from app.core.database import async_session_factory
from app.modules.census.domain.population import CensusReconciliationError
from app.modules.census.infrastructure.loaders import (
    DEFAULT_RAW_DIR,
    CensusIngestionError,
    ingest_census,
)


async def run(arguments: argparse.Namespace) -> int:
    """Execute the ingestion and print the observed outcome of every step."""
    raw_dir = Path(arguments.raw_dir).resolve()
    if not raw_dir.is_dir():
        print(
            f"Corpus directory {raw_dir} does not exist. "
            f"Run 'uv run python -m scripts.download_census' first.",
            file=sys.stderr,
        )
        return 2

    print(f"Corpus: {raw_dir}")
    print(f"Segments: {'skipped' if arguments.skip_segments else 'included'}")
    print(f"Mode: {'dry run (rolled back)' if arguments.dry_run else 'commit'}")
    started = time.monotonic()

    async with async_session_factory() as session:
        try:
            report = await ingest_census(
                session,
                raw_dir=raw_dir,
                include_segments=not arguments.skip_segments,
                commit=not arguments.dry_run,
            )
        except (CensusIngestionError, CensusReconciliationError) as exc:
            await session.rollback()
            print(f"INGESTION FAILED: {exc}", file=sys.stderr)
            return 1
        if arguments.dry_run:
            await session.rollback()

    for line in report.lines():
        print(f"  {line}")
    print(f"Completed in {time.monotonic() - started:.1f}s")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        prog="ingest_census",
        description=(
            "Load the CPV 2024 corpus into PostGIS. Idempotent; asserts per-layer "
            "unit counts and the national population reconciliation."
        ),
        epilog=(
            "Run from the backend/ directory with PostGIS up: "
            "uv run python -m scripts.ingest_census"
        ),
    )
    parser.add_argument(
        "--raw-dir",
        default=str(DEFAULT_RAW_DIR),
        help="Corpus directory (default: %(default)s)",
    )
    parser.add_argument(
        "--skip-segments",
        action="store_true",
        help="Skip the 10,290 census segment polygons (geometry-only context)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and reconcile, then roll back instead of committing",
    )
    return parser


def main() -> int:
    """Entry point."""
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
