"""Regenerate ``data/census/raw/`` from the public BCR/ONEC ArcGIS REST API.

The raw corpus (~570 MB, 16 layers) is gitignored, so it must be reproducible from
scratch. This script is idempotent and resumable: completed files are verified and
skipped, and an interrupted layer resumes from the last page it finished.

Usage
-----
Run it from the ``backend/`` directory so both ``app`` and ``scripts`` resolve::

    # Download everything missing, verifying row counts (the normal case).
    uv run python -m scripts.download_census

    # See what would happen without touching the network beyond row counts.
    uv run python -m scripts.download_census --dry-run

    # Re-download specific layers, discarding what is on disk.
    uv run python -m scripts.download_census --force \\
        --layer degurba_densidad.geojson --layer segmentos_censales_2024.geojson

    # Write somewhere else (useful for a side-by-side comparison).
    uv run python -m scripts.download_census --raw-dir /tmp/census-check

    # List the organization's Feature Services, to audit the catalogue.
    uv run python -m scripts.download_census --list-services

Behaviour
---------
For every catalogue entry the script asks ArcGIS for the layer's exact row count
and refuses to proceed when it disagrees with the verified count recorded in
``app.modules.census.domain.catalog`` -- a drift there means the published census
changed and the ingestion assertions need review. Pass ``--allow-count-drift``
to download anyway.

Pages are written to ``<raw-dir>/.parts/<filename>/page_<offset>.json`` and only
assembled into the final file once every page is present, so a partially written
layer is never mistaken for a complete one. Assembly is atomic: a temporary file
is renamed over the target. Part files are removed on success unless
``--keep-parts`` is given.
"""

import argparse
import asyncio
import csv
import json
import os
from pathlib import Path
import sys
from typing import Any

from app.modules.census.domain.catalog import (
    ARCGIS_ORG_ID,
    ARCGIS_ORG_SLUG,
    CENSUS_LAYERS,
    CensusLayer,
    layer_by_filename,
)
from app.modules.census.infrastructure.arcgis_client import (
    ArcGisFeatureServiceClient,
    ArcGisPage,
    ArcGisQueryError,
)
from app.modules.census.infrastructure.geojson_stream import (
    GeoJsonStreamError,
    count_geojson_features,
    iter_geojson_feature_texts,
)
from app.modules.census.infrastructure.loaders import DEFAULT_RAW_DIR

PARTS_DIRNAME = ".parts"
MANIFEST_FILENAME = "manifest.json"
GEOJSON_HEADER = '{"type":"FeatureCollection","features":['
GEOJSON_FOOTER = "]}\n"


def _parts_dir(raw_dir: Path, layer: CensusLayer) -> Path:
    """Return the per-layer directory holding downloaded pages."""
    return raw_dir / PARTS_DIRNAME / layer.filename


def _page_path(raw_dir: Path, layer: CensusLayer, offset: int) -> Path:
    """Return the cache path of one downloaded page."""
    return _parts_dir(raw_dir, layer) / f"page_{offset:08d}.json"


def _existing_row_count(path: Path) -> int | None:
    """Return the row count of an already-downloaded file, or None if unreadable."""
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        if path.suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return max(sum(1 for _ in csv.reader(handle)) - 1, 0)
        return count_geojson_features(path)
    except (GeoJsonStreamError, UnicodeDecodeError, OSError):
        return None


def _load_cached_page(path: Path) -> ArcGisPage | None:
    """Return a cached page when it is present and parseable."""
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        body = path.read_text(encoding="utf-8")
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    features = payload.get("features")
    if not isinstance(features, list):
        return None
    offset = int(path.stem.split("_")[-1])
    return ArcGisPage(
        offset=offset,
        body=body,
        feature_count=len(features),
        exceeded_transfer_limit=bool(payload.get("exceededTransferLimit")),
    )


def _assemble_geojson(raw_dir: Path, layer: CensusLayer, pages: list[Path]) -> int:
    """Concatenate page files into one FeatureCollection, atomically."""
    target = raw_dir / layer.filename
    temporary = target.with_suffix(target.suffix + ".tmp")
    written = 0
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(GEOJSON_HEADER)
        for page_path in pages:
            for feature_text in iter_geojson_feature_texts(page_path):
                if written:
                    handle.write(",")
                handle.write(feature_text)
                written += 1
        handle.write(GEOJSON_FOOTER)
    os.replace(temporary, target)
    return written


def _assemble_csv(raw_dir: Path, layer: CensusLayer, pages: list[Path]) -> int:
    """Flatten ArcGIS attribute pages into one CSV, atomically."""
    target = raw_dir / layer.filename
    temporary = target.with_suffix(target.suffix + ".tmp")
    field_names: list[str] = []
    rows: list[dict[str, Any]] = []
    for page_path in pages:
        payload = json.loads(page_path.read_text(encoding="utf-8"))
        for descriptor in payload.get("fields") or []:
            name = descriptor.get("name")
            if name and name not in field_names:
                field_names.append(name)
        for feature in payload.get("features") or []:
            attributes = feature.get("attributes") or {}
            for name in attributes:
                if name not in field_names:
                    field_names.append(name)
            rows.append(attributes)

    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, target)
    return len(rows)


async def download_layer(
    client: ArcGisFeatureServiceClient,
    layer: CensusLayer,
    raw_dir: Path,
    force: bool = False,
    dry_run: bool = False,
    allow_count_drift: bool = False,
    keep_parts: bool = False,
) -> str:
    """Download one layer, resuming and verifying, and return a status line."""
    server_count = await client.count_features(layer)
    if server_count != layer.expected_feature_count:
        message = (
            f"{layer.filename}: ArcGIS reports {server_count} rows but the "
            f"catalogue records {layer.expected_feature_count}. The published "
            f"census changed; review the ingestion assertions."
        )
        if not allow_count_drift:
            raise ArcGisQueryError(message)
        print(f"  WARNING {message}", file=sys.stderr)

    target = raw_dir / layer.filename
    if not force:
        existing = _existing_row_count(target)
        if existing == server_count:
            return f"{layer.filename}: already complete ({existing} rows)"
        if existing is not None:
            print(
                f"  {layer.filename}: on disk has {existing} rows, expected "
                f"{server_count}; re-downloading",
                file=sys.stderr,
            )

    if dry_run:
        return f"{layer.filename}: would download {server_count} rows"

    parts = _parts_dir(raw_dir, layer)
    parts.mkdir(parents=True, exist_ok=True)
    if force:
        for stale in sorted(parts.glob("page_*.json")):
            stale.unlink()

    offset = 0
    page_paths: list[Path] = []
    while offset < server_count:
        page_path = _page_path(raw_dir, layer, offset)
        cached = _load_cached_page(page_path)
        if cached is not None:
            page_paths.append(page_path)
            offset += cached.feature_count
            continue
        page = await client.fetch_page(layer, offset=offset)
        if page.feature_count == 0:
            raise ArcGisQueryError(
                f"{layer.filename}: empty page at offset {offset} while "
                f"{server_count - offset} rows were still expected"
            )
        page_path.write_text(page.body, encoding="utf-8")
        page_paths.append(page_path)
        offset += page.feature_count

    if layer.filename.endswith(".csv"):
        written = _assemble_csv(raw_dir, layer, page_paths)
    else:
        written = _assemble_geojson(raw_dir, layer, page_paths)

    if written != server_count:
        raise ArcGisQueryError(
            f"{layer.filename}: assembled {written} rows but ArcGIS reported "
            f"{server_count}. Refusing to leave a short file in place."
        )

    (parts / MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "filename": layer.filename,
                "service": layer.service_name,
                "layer_id": layer.layer_id,
                "rows": written,
                "page_size": layer.page_size,
                "out_sr": 4326,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if not keep_parts:
        for page_path in page_paths:
            page_path.unlink(missing_ok=True)

    return f"{layer.filename}: downloaded {written} rows"


async def list_services(client: ArcGisFeatureServiceClient) -> None:
    """Print every public Feature Service of the organization."""
    items = await client.search_feature_services()
    print(f"{len(items)} Feature Services in org {ARCGIS_ORG_SLUG} ({ARCGIS_ORG_ID})")
    for item in sorted(items, key=lambda entry: str(entry.get("title"))):
        service = str(item.get("url") or "").split("/services/")[-1]
        print(f"  {item.get('title')}  ->  {service}")


async def run(arguments: argparse.Namespace) -> int:
    """Execute the requested download and report per-layer outcomes."""
    raw_dir = Path(arguments.raw_dir).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)

    selected: tuple[CensusLayer, ...]
    if arguments.layer:
        selected = tuple(layer_by_filename(name) for name in arguments.layer)
    else:
        selected = CENSUS_LAYERS

    failures = 0
    async with ArcGisFeatureServiceClient(
        timeout_seconds=arguments.timeout
    ) as client:
        if arguments.list_services:
            await list_services(client)
            return 0

        print(f"Target directory: {raw_dir}")
        print(f"Layers: {len(selected)}")
        for layer in selected:
            try:
                print(
                    await download_layer(
                        client,
                        layer,
                        raw_dir,
                        force=arguments.force,
                        dry_run=arguments.dry_run,
                        allow_count_drift=arguments.allow_count_drift,
                        keep_parts=arguments.keep_parts,
                    )
                )
            except (ArcGisQueryError, GeoJsonStreamError, OSError) as exc:
                failures += 1
                print(f"{layer.filename}: FAILED {exc}", file=sys.stderr)

    if failures:
        print(f"{failures} layer(s) failed", file=sys.stderr)
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        prog="download_census",
        description=(
            "Regenerate data/census/raw/ from the public BCR/ONEC ArcGIS REST API. "
            "Idempotent and resumable; verifies every layer's row count."
        ),
        epilog=(
            "Run from the backend/ directory: "
            "uv run python -m scripts.download_census"
        ),
    )
    parser.add_argument(
        "--raw-dir",
        default=str(DEFAULT_RAW_DIR),
        help="Destination directory (default: %(default)s)",
    )
    parser.add_argument(
        "--layer",
        action="append",
        default=[],
        metavar="FILENAME",
        help="Restrict to one catalogue filename; repeatable",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Discard cached pages and existing files, then download again",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what each layer would do without downloading features",
    )
    parser.add_argument(
        "--allow-count-drift",
        action="store_true",
        help="Warn instead of failing when ArcGIS row counts changed",
    )
    parser.add_argument(
        "--keep-parts",
        action="store_true",
        help="Keep per-page cache files after a successful assembly",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Per-request timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--list-services",
        action="store_true",
        help="List the organization's Feature Services and exit",
    )
    return parser


def main() -> int:
    """Entry point."""
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
