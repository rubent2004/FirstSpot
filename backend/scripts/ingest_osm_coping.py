"""Download and ingest the national OpenStreetMap coping-capacity corpus.

Why a pinned national extract rather than the live Overpass path
---------------------------------------------------------------
The existing Overpass ingestion answers "what can a responder use near this
point", zone by zone. Measured on the ingested corpus it leaves **24 of 262
districts with any place at all and 21 with a hospital or clinic**, and the
consequence for an index is not a gap but a lie: computing distance-to-care
against that corpus gives a national mean of **27.8 km** and a maximum of 65.0
km, against **3.8 km** and 20.3 km on complete national data. The 27.8 km figure
measures how far a district is from the seven zones that were queried, and it
would have ranked districts plausibly -- worst for the remote ones -- for
entirely the wrong reason.

The Geofabrik country extract fixes coverage and reproducibility in one move:
184 hospitals, 518 clinics, 18 fire stations, 1,199 schools, 153 community
centres and 2,506 primary-network ways, from a **pinned file** rather than a live
API whose answer changes between two runs for reasons unrelated to the territory.

Idempotence
-----------
The corpus is replaced wholesale on every run, because the upstream extract is
rebuilt daily and a hospital OSM has deleted must disappear from our copy too.
Re-running with the same file therefore produces the same table contents and the
same cached measurements.
"""

import argparse
import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.ingestion.domain.osm_extract import (
    OSM_SNAPSHOT_LICENCE,
    OSM_SNAPSHOT_SOURCE,
    OSM_SNAPSHOT_URL,
)
from app.modules.ingestion.infrastructure.osm_coping_loader import (
    OsmCopingLoader,
)
from app.modules.ingestion.infrastructure.osm_pbf_reader import (
    OsmExtractError,
    OsmPbfReader,
)
from app.modules.prioritization.domain.coping import ACCESS_THRESHOLD_METRES
from app.modules.prioritization.infrastructure.coping_repository import (
    ANALYSIS_DUG_LEVEL,
)

DEFAULT_EXTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "osm"
    / "raw"
    / "el-salvador-latest.osm.pbf"
)
"""Where the extract lives. Gitignored: it is 35 MB and regenerable."""

DOWNLOAD_TIMEOUT_SECONDS = 600.0
"""Generous: the file is 35 MB and Geofabrik throttles under load."""


def download(destination: Path, url: str) -> int:
    """Fetch the extract to a temporary name, then rename it into place.

    The rename is the point. A half-downloaded ``.osm.pbf`` left at the final
    path would be read on the next run and would parse as a valid but truncated
    extract -- silently losing whichever facilities fall after the cut.
    """
    import httpx

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    written = 0
    with httpx.stream(
        "GET", url, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT_SECONDS
    ) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
                written += len(chunk)
    partial.replace(destination)
    return written


def _snapshot_date(path: Path, override: str | None) -> date:
    """Date the extract represents.

    Geofabrik rebuilds daily and does not embed a usable build date in the file
    header that pyosmium exposes cheaply, so the file's own modification time is
    the honest default and ``--snapshot-date`` exists for a reproducible run.
    """
    if override:
        return date.fromisoformat(override)
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()


async def run(arguments: argparse.Namespace) -> int:
    """Download if asked, read the extract, and load it with its access cache."""
    path = Path(arguments.extract).expanduser().resolve()

    if arguments.download or not path.exists():
        print(f"Downloading {OSM_SNAPSHOT_URL}")
        try:
            size = download(path, OSM_SNAPSHOT_URL)
        except Exception as exc:
            print(f"Download failed: {exc}", file=sys.stderr)
            return 1
        print(f"  wrote {size / 1_048_576:.1f} MiB to {path}")

    if arguments.dry_run:
        try:
            contents = OsmPbfReader(path).read()
        except OsmExtractError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Extract      {path}")
        print(f"Snapshot     {_snapshot_date(path, arguments.snapshot_date)}")
        print(f"Source       {OSM_SNAPSHOT_SOURCE} ({OSM_SNAPSHOT_LICENCE})")
        print(
            f"Parsed       {contents.node_count} nodes, "
            f"{contents.way_count} ways, {contents.relation_count} relations"
        )
        for kind, count in sorted(contents.facility_counts().items()):
            print(f"  {kind:18s} {count}")
        print(f"  primary roads      {len(contents.roads)}")
        if contents.degenerate_way_count:
            print(
                f"  unusable ways      {contents.degenerate_way_count} "
                f"(fewer than two locatable nodes; clipped at the border)"
            )
        print("Dry run: nothing written.")
        return 0

    try:
        contents = OsmPbfReader(path).read()
    except OsmExtractError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    engine = create_async_engine(settings.database_url, echo=False)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as session:
            report = await OsmCopingLoader(session).load(
                facilities=contents.facilities,
                roads=contents.roads,
                snapshot_date=_snapshot_date(path, arguments.snapshot_date),
                access_threshold_metres=arguments.threshold,
                dug_level=ANALYSIS_DUG_LEVEL,
            )
    finally:
        await engine.dispose()

    print(f"Snapshot     {report.snapshot_date}")
    print(f"Source       {OSM_SNAPSHOT_SOURCE} ({OSM_SNAPSHOT_LICENCE})")
    print(f"Facilities   {report.facilities_loaded}")
    for kind, count in sorted(report.facility_counts.items()):
        print(f"  {kind:18s} {count}")
    print(f"Roads        {report.roads_loaded} primary-network ways")
    print(f"Access rows  {report.access_rows} DEGURBA Nivel 2 polygons")
    print(f"Threshold    {arguments.threshold} m (context shares only)")
    print(f"Elapsed      {report.elapsed_seconds:.1f}s")
    print(
        "Distances are GEODESIC: true ellipsoidal metres, and a LOWER BOUND on "
        "travel distance. pgRouting is not installed, so nothing here is a route."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        description=(
            "Ingest the national OpenStreetMap coping-capacity corpus and "
            "refresh the cached per-polygon access measurements behind PRIO-SV's "
            "Lack of Coping Capacity dimension."
        )
    )
    parser.add_argument(
        "--extract",
        default=str(DEFAULT_EXTRACT_PATH),
        help="Path to el-salvador-latest.osm.pbf (default: data/osm/raw/).",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help=(
            "Re-download the extract from Geofabrik even when it is already "
            "present. It is fetched automatically when absent."
        ),
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=ACCESS_THRESHOLD_METRES,
        help=(
            "Fixed distance in metres defining 'beyond reach on foot' for the "
            "published context shares (default: %(default)s, about one hour's "
            "walk per Sphere 2018). The two index variables are mean distances "
            "and do not use it."
        ),
    )
    parser.add_argument(
        "--snapshot-date",
        default=None,
        help=(
            "ISO date the extract represents (default: the file's modification "
            "time). Set it for a reproducible run against an archived extract."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report what would be loaded, without writing.",
    )
    return parser


def main() -> int:
    """Entry point for ``python -m scripts.ingest_osm_coping``."""
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
