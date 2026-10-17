"""USGS ShakeMap and PAGER: the per-event hazard input, and what it may never say.

This module turns three USGS payloads into domain objects and refuses to turn
them into anything else. It is the only place in PRIO-SV that reads a live
per-event feed, which is why the discipline here is about **what a number is
allowed to claim** rather than about arithmetic.

The three payloads, and why each one
------------------------------------
``fdsnws/event/1/query?format=geojson``
    The event catalogue. No API key, bounded by a bounding box and a minimum
    magnitude. Yields :class:`EarthquakeEventSummary`, including whether a
    ShakeMap and a PAGER product exist, so a caller never requests a detail
    document to discover that the event has no shaking model.
``fdsnws/event/1/query?eventid=<id>&format=geojson``
    The detail document, which carries ``properties.products``. The documented
    ``earthquakes/feed/v1.0/detail/<id>.geojson`` path **302-redirects here**, so
    the canonical form is used directly and a client that does not follow
    redirects still works.
``products.shakemap[0].contents["download/cont_mi.json"]``
    The MMI contours, as GeoJSON ``MultiLineString`` iso-lines. The full
    MMI/PGA/PGV grid lives in ``download/grid.xml`` and is 27 MB for a single
    historical event, against 51 KB for the contours; the ShakeMap metadata
    carries ``maximum-latitude`` and ``maxmmi`` so an irrelevant event can be
    rejected before either is fetched.

Contours bound areas, and that takes one decision
-------------------------------------------------
``cont_mi.json`` publishes **lines, not polygons**. The region enclosed by the
iso-line of value *v* is the region whose intensity is at least *v*, for a field
that decays away from its source, so a closed ring is the boundary of an
"MMI >= v" area and an **open** ring -- one clipped by the edge of the grid --
bounds nothing at all. :func:`parse_mmi_bands` therefore keeps only closed rings
carrying at least four coordinates, because a ring of three coordinates whose
first equals its last has two distinct points and encloses zero area.

Verified on the 13 February 2001 M6.6 Cojutepeque event: every contour at or
above MMI 4 is closed, and the areas nest monotonically from 18,852 km² at MMI 4
down to 286 km² at MMI 7. The open rings are all at MMI 2 to 3.5, below the
declared floor, so the floor and the closure filter remove the same features.

The contour ceiling understates the peak, and that is published
---------------------------------------------------------------
Contours are drawn at a fixed interval -- 0.5 MMI in every ShakeMap inspected --
so the highest *drawn* contour sits below the grid's true maximum. The same 2001
event declares ``maxmmi`` 7.504 while its highest contour is 7.0. A maximum taken
from contours is therefore short by **up to one contour interval**, and the
direction is not conservative for a prioritisation tool: it understates hazard,
and therefore priority. :attr:`ShakeMapRelease.declared_max_mmi` and
:attr:`ShakeMapRelease.contour_interval` travel with every release so the gap is
visible and bounded rather than invisible.

What this module must never produce
-----------------------------------
PAGER is **probabilistic** and publishes roughly 30 minutes after an event, while
"information on the extent of shaking will be uncertain". It estimates a
*distribution* over fatalities and shipping losses, and its alert level is a band
rather than a count. Nothing derived from it may be reported as casualties,
victims or deaths: see :data:`CASUALTY_REPORTING_PROHIBITION`. What may be
reported is the **alert level with its published range** -- orange means 100-999
estimated fatalities -- and the **estimated exposed population**, which is a
population count under a shaking threshold and not a prediction about anybody.

ShakeMap is also **revised**: the same event id yields a different grid as data
arrives, and historical events are reprocessed into the ShakeMap Atlas years
later. Every figure derived from a grid is therefore stamped with
:attr:`ShakeMapRelease.grid_processed_at`; see
:data:`SHAKEMAP_REVISION_WARNING`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

MMI_SCALE_FLOOR = Decimal(4)
"""Modified Mercalli intensity that scores zero hazard intensity.

A **fixed declared bound**, chosen once and never derived from an event's observed
range. MMI IV is "light" shaking: felt indoors, windows and dishes rattle, no
structural damage. Below it there is nothing for a response to prioritise, so the
floor of the intensity scale sits here and a district whose maximum is exactly IV
scores exactly zero.
"""

MMI_SCALE_CEILING = Decimal(10)
"""Modified Mercalli intensity that scores ten.

Also fixed, and deliberately beyond anything El Salvador has recorded in the
USGS catalogue -- the 2001 M6.6 inland event peaked at MMI 7.5. The cost is that
a typical Salvadoran earthquake uses only the lower half of the intensity range,
and the benefit is that two events, and the same event over time, are directly
comparable. Anchoring the ceiling to an event's own maximum would make a district
appear to improve because a different district got worse, which is the single
defect this index exists to avoid.
"""

EXPOSURE_MMI_THRESHOLD = Decimal(6)
"""Intensity at or above which a person counts as exposed.

MMI VI is the threshold at which shaking is felt by everyone, objects fall and
damage begins -- the lowest intensity at which a population has a response need
rather than an experience. A **fixed bound**, like the two above.
"""

MMI_CONTOUR_CONTENT_KEY = "download/cont_mi.json"
"""ShakeMap product content holding the MMI iso-lines as GeoJSON."""

MMI_GRID_CONTENT_KEY = "download/grid.xml"
"""ShakeMap product content holding the full MMI/PGA/PGV grid.

Not fetched. It is 27 MB for one historical event against 51 KB for the contours,
and the contours answer the question this index asks. Recorded here so the
trade-off is visible, and because the grid is what a future per-cell exposure
measurement would need.
"""

USGS_EVENT_QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
"""FDSN event service. No API key, verified 2026-10-17."""

USGS_ATTRIBUTION = (
    "U.S. Geological Survey, Earthquake Hazards Program -- FDSN event service, "
    "ShakeMap and PAGER. Public domain, no API key required."
)
"""Provenance published with every hazard response."""

CASUALTY_REPORTING_PROHIBITION = (
    "This system never reports casualties, victims or deaths, and no number it "
    "publishes may be presented as one. PAGER is probabilistic: it estimates a "
    "distribution over fatalities and economic losses from modelled shaking and "
    "modelled building stock, it publishes about 30 minutes after an event when "
    "information on the extent of shaking is still uncertain, and it is revised. "
    "What is published instead is the PAGER alert LEVEL with its own declared "
    "range -- orange means an estimated 100-999 fatalities, and the range is part "
    "of the figure, never a point value -- and the estimated exposed population, "
    "which is a count of residents living where modelled intensity reaches the "
    "declared threshold. An exposed person is a person a response has to reach, "
    "not a person predicted to be harmed."
)
"""The reporting contract, published with every hazard and index response."""

SHAKEMAP_REVISION_WARNING = (
    "ShakeMap is revised. The same event id yields a different grid as stations "
    "report and as finite-fault and site-amplification models are updated, and "
    "historical events are reprocessed into the ShakeMap Atlas years afterwards. "
    "Every figure derived from a grid therefore carries that grid's process "
    "timestamp, and two figures with different timestamps are not comparable even "
    "for the same earthquake. A hazard number quoted without its grid time is "
    "undated."
)
"""Published beside every ShakeMap-derived figure."""

CONTOUR_INTERVAL_DEFAULT = Decimal("0.5")
"""Contour spacing observed in every ShakeMap ``cont_mi.json`` inspected.

Derived from the parsed band values when at least two exist, and used as the
declared fallback when a single band leaves no spacing to measure.
"""


class ShakeMapError(ValueError):
    """Raised when a USGS payload cannot be read as a ShakeMap input."""


@dataclass(frozen=True, slots=True)
class PagerAlertBand:
    """One PAGER alert level with the fatality range it stands for.

    The range is the figure. A level published without it invites a reader to
    substitute a point estimate, which is exactly the claim
    :data:`CASUALTY_REPORTING_PROHIBITION` forbids.
    """

    level: str
    lower_bound: int
    upper_bound: int | None
    label: str
    response_implication: str


PAGER_ALERT_BANDS: tuple[PagerAlertBand, ...] = (
    PagerAlertBand(
        level="green",
        lower_bound=0,
        upper_bound=0,
        label="0 estimated fatalities (PAGER green)",
        response_implication=(
            "No estimated fatalities and little estimated economic loss. Local "
            "response is normally sufficient."
        ),
    ),
    PagerAlertBand(
        level="yellow",
        lower_bound=1,
        upper_bound=99,
        label="1-99 estimated fatalities (PAGER yellow)",
        response_implication=(
            "A local or regional response. The range spans two orders of "
            "magnitude and is not a count."
        ),
    ),
    PagerAlertBand(
        level="orange",
        lower_bound=100,
        upper_bound=999,
        label="100-999 estimated fatalities (PAGER orange)",
        response_implication=(
            "A national response is normally required. The range is the figure; "
            "no point value inside it is published."
        ),
    ),
    PagerAlertBand(
        level="red",
        lower_bound=1000,
        upper_bound=None,
        label="1000 or more estimated fatalities (PAGER red)",
        response_implication=(
            "An international response is normally required. The band is "
            "open-ended above."
        ),
    ),
)
"""The four published PAGER alert levels with their declared ranges."""


def pager_alert_band(level: str | None) -> PagerAlertBand | None:
    """Return the declared band for a PAGER level, or None for anything else.

    An unrecognised level yields None rather than a guess or a green default: a
    level this code does not know is an unknown alert, and publishing it as "no
    expected fatalities" would be the most dangerous possible error.
    """
    if not level:
        return None
    normalised = level.strip().lower()
    return next(
        (band for band in PAGER_ALERT_BANDS if band.level == normalised), None
    )


@dataclass(frozen=True, slots=True)
class PagerAlert:
    """One event's PAGER alert, as a level and a range and never as a count."""

    level: str
    band_label: str
    lower_bound: int
    upper_bound: int | None
    response_implication: str
    max_mmi: Decimal | None
    published_at: datetime | None
    reporting_contract: str = CASUALTY_REPORTING_PROHIBITION


@dataclass(frozen=True, slots=True)
class MmiBand:
    """The closed iso-line bounding the area whose intensity is at least ``mmi``.

    ``geometry`` is a GeoJSON ``MultiLineString`` of closed rings, kept in the
    source's own form so that PostGIS builds the area with ``ST_BuildArea``
    rather than this module guessing at ring nesting. A ring nested inside
    another ring of the same value is a hole, and ``ST_BuildArea`` resolves that
    correctly where a hand-built ``MultiPolygon`` would double-count it.
    """

    mmi: Decimal
    ring_count: int
    geometry: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EarthquakeEventSummary:
    """One catalogue entry, with enough to decide whether to fetch its detail."""

    event_id: str
    magnitude: Decimal | None
    place: str
    latitude: Decimal
    longitude: Decimal
    depth_km: Decimal | None
    occurred_at: datetime
    has_shakemap: bool
    has_pager: bool
    url: str | None


@dataclass(frozen=True, slots=True)
class ShakeMapRelease:
    """One ShakeMap grid release, identified by the time it was processed."""

    event_id: str
    magnitude: Decimal | None
    place: str
    latitude: Decimal
    longitude: Decimal
    depth_km: Decimal | None
    occurred_at: datetime
    grid_processed_at: datetime | None
    version: str | None
    map_status: str | None
    declared_max_mmi: Decimal | None
    declared_max_pga: Decimal | None
    contour_interval: Decimal | None
    bands: tuple[MmiBand, ...]
    contour_url: str | None
    pager: PagerAlert | None
    attribution: str = USGS_ATTRIBUTION
    revision_warning: str = SHAKEMAP_REVISION_WARNING
    reporting_contract: str = CASUALTY_REPORTING_PROHIBITION

    @property
    def contour_max_mmi(self) -> Decimal | None:
        """Highest drawn contour, which is at most the grid's true maximum."""
        return max((band.mmi for band in self.bands), default=None)


def _decimal(value: Any) -> Decimal | None:
    """Carry a JSON number into Decimal without inheriting float noise."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _epoch_ms(value: Any) -> datetime | None:
    """Read a USGS millisecond epoch as an aware UTC datetime."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _iso(value: Any) -> datetime | None:
    """Read a USGS ISO-8601 timestamp, normalising the trailing Z."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _product_types(properties: dict[str, Any]) -> set[str]:
    """Read the comma-delimited ``types`` field of a catalogue entry.

    USGS wraps the list in leading and trailing commas, so a naive split yields
    empty strings; the filter is what makes ``has_shakemap`` reliable.
    """
    raw = properties.get("types") or ""
    return {part for part in str(raw).split(",") if part}


def parse_event_summaries(
    payload: dict[str, Any],
) -> tuple[EarthquakeEventSummary, ...]:
    """Parse an FDSN GeoJSON FeatureCollection into event summaries.

    A feature without usable coordinates is dropped rather than defaulted: an
    earthquake at (0, 0) off the coast of Ghana would silently enter a Salvadoran
    event list.
    """
    summaries: list[EarthquakeEventSummary] = []
    for feature in payload.get("features") or []:
        properties = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coordinates) < 2:
            continue
        longitude = _decimal(coordinates[0])
        latitude = _decimal(coordinates[1])
        if longitude is None or latitude is None:
            continue
        occurred_at = _epoch_ms(properties.get("time"))
        if occurred_at is None:
            continue
        types = _product_types(properties)
        summaries.append(
            EarthquakeEventSummary(
                event_id=str(feature.get("id") or ""),
                magnitude=_decimal(properties.get("mag")),
                place=str(properties.get("place") or properties.get("title") or ""),
                latitude=latitude,
                longitude=longitude,
                depth_km=(
                    _decimal(coordinates[2]) if len(coordinates) >= 3 else None
                ),
                occurred_at=occurred_at,
                has_shakemap="shakemap" in types,
                has_pager="losspager" in types,
                url=(
                    str(properties["url"]) if properties.get("url") else None
                ),
            )
        )
    return tuple(summaries)


def _detail_feature(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the single feature of a detail document, whichever shape it has.

    ``?eventid=`` returns a bare Feature; the same service returns a
    FeatureCollection for a query. Accepting both means a caller that reused a
    query response does not get a confusing KeyError three frames down.
    """
    if payload.get("type") == "FeatureCollection":
        features = payload.get("features") or []
        if not features:
            raise ShakeMapError(
                "The USGS detail document holds no feature, so it describes no "
                "event. A query that matched nothing returns this shape."
            )
        return features[0]
    return payload


def _shakemap_product(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the first ShakeMap product, refusing an event that has none."""
    feature = _detail_feature(payload)
    products = ((feature.get("properties") or {}).get("products")) or {}
    shakemaps = products.get("shakemap") or []
    if not shakemaps:
        raise ShakeMapError(
            "This event publishes no ShakeMap product, so no modelled intensity "
            "exists for it and the Hazard & Exposure dimension cannot be "
            "measured. Most small and many offshore events never get one; the "
            "event catalogue publishes `has_shakemap` so this is checkable "
            "before the detail document is fetched."
        )
    return shakemaps[0]


def mmi_contour_url(payload: dict[str, Any]) -> str:
    """Return the download URL of an event's MMI contour GeoJSON.

    Raises:
        ShakeMapError: If the event has no ShakeMap, or its ShakeMap has no
            contour content. Both are refusals rather than fallbacks: deriving
            intensity from a different product would publish a number under a
            label that does not describe it.
    """
    product = _shakemap_product(payload)
    content = (product.get("contents") or {}).get(MMI_CONTOUR_CONTENT_KEY)
    if not content or not content.get("url"):
        raise ShakeMapError(
            f"This event's ShakeMap publishes no {MMI_CONTOUR_CONTENT_KEY}, so "
            f"its MMI iso-lines are unavailable. The full grid at "
            f"{MMI_GRID_CONTENT_KEY} is not substituted: it is a different "
            f"product with a different resolution, and silently swapping it "
            f"would change what the published intensity means."
        )
    return str(content["url"])


def parse_mmi_bands(
    payload: dict[str, Any],
    floor: Decimal = MMI_SCALE_FLOOR,
) -> tuple[MmiBand, ...]:
    """Parse ``cont_mi.json`` into the closed bands at or above ``floor``.

    Args:
        payload: The ShakeMap MMI contour GeoJSON FeatureCollection.
        floor: Lowest MMI to keep. Defaults to the declared scale floor, below
            which there is no hazard to prioritise.

    Returns:
        One band per contour value, ascending, each holding only closed rings of
        at least four coordinates.

    Raises:
        ShakeMapError: If no contour at or above the floor bounds any area. That
            is a real outcome for a small or distant event, and it is an error
            rather than an empty result because an empty band list would score
            every district zero and look like a successful computation.
    """
    bands: list[MmiBand] = []
    for feature in payload.get("features") or []:
        value = _decimal((feature.get("properties") or {}).get("value"))
        if value is None or value < floor:
            continue
        geometry = feature.get("geometry") or {}
        parts = geometry.get("coordinates") or []
        if geometry.get("type") == "LineString":
            parts = [parts]
        # A ring of three coordinates whose first equals its last has two
        # distinct points and encloses nothing; an unclosed ring was clipped by
        # the edge of the grid and bounds nothing either.
        rings = [
            [list(point) for point in ring]
            for ring in parts
            if len(ring) >= 4 and list(ring[0]) == list(ring[-1])
        ]
        if not rings:
            continue
        bands.append(
            MmiBand(
                mmi=value,
                ring_count=len(rings),
                geometry={"type": "MultiLineString", "coordinates": rings},
            )
        )
    if not bands:
        raise ShakeMapError(
            f"This ShakeMap publishes no closed MMI contour at or above "
            f"{floor}, so no area reaches the declared intensity floor and the "
            f"event shook nobody this index can measure. An empty band set is "
            f"refused rather than returned, because scoring every district zero "
            f"would be indistinguishable from a successful computation."
        )
    return tuple(sorted(bands, key=lambda band: band.mmi))


def _contour_interval(bands: Sequence[MmiBand]) -> Decimal:
    """Return the spacing between contour values, for the discretisation bound."""
    if len(bands) < 2:
        return CONTOUR_INTERVAL_DEFAULT
    return min(
        upper.mmi - lower.mmi for lower, upper in zip(bands, bands[1:])
    )


def _parse_pager(products: dict[str, Any]) -> PagerAlert | None:
    """Read a PAGER product as a level and a range, or publish its absence.

    An event with no PAGER returns None, never a green alert. PAGER began in
    2007, so every historical Salvadoran earthquake before then has no alert at
    all, and "no estimate exists" must not render as "no expected fatalities".
    """
    entries = products.get("losspager") or []
    if not entries:
        return None
    properties = entries[0].get("properties") or {}
    band = pager_alert_band(properties.get("alertlevel"))
    if band is None:
        return None
    return PagerAlert(
        level=band.level,
        band_label=band.label,
        lower_bound=band.lower_bound,
        upper_bound=band.upper_bound,
        response_implication=band.response_implication,
        max_mmi=_decimal(properties.get("maxmmi")),
        published_at=(
            _iso(properties.get("eventtime"))
            or _epoch_ms(entries[0].get("updateTime"))
        ),
    )


def parse_shakemap_release(
    detail_payload: dict[str, Any],
    contour_payload: dict[str, Any],
) -> ShakeMapRelease:
    """Assemble one ShakeMap release from a detail document and its contours.

    The release is the unit of identity for everything downstream: a hazard score
    belongs to a *grid*, not to an earthquake, because the same earthquake yields
    a different grid on revision. :attr:`ShakeMapRelease.grid_processed_at` is
    what a consumer compares, and it is read from the ShakeMap product's own
    ``process-timestamp`` rather than from the event's origin time.

    Raises:
        ShakeMapError: If the event publishes no ShakeMap, or its contours hold
            no closed band at or above the declared floor.
    """
    feature = _detail_feature(detail_payload)
    properties = feature.get("properties") or {}
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coordinates) < 2:
        raise ShakeMapError(
            "The USGS detail document carries no epicentre coordinates, so the "
            "event cannot be located and nothing may be attributed to it."
        )
    product = _shakemap_product(detail_payload)
    product_properties = product.get("properties") or {}
    bands = parse_mmi_bands(contour_payload)
    occurred_at = _epoch_ms(properties.get("time"))
    if occurred_at is None:
        raise ShakeMapError(
            "The USGS detail document carries no origin time. Every published "
            "hazard figure is stamped, so an undated event is refused."
        )
    contour_url = None
    try:
        contour_url = mmi_contour_url(detail_payload)
    except ShakeMapError:
        # The contours were supplied directly, which is the recorded-fixture and
        # offline path. Their absence from the product index is not fatal here.
        contour_url = None

    return ShakeMapRelease(
        event_id=str(feature.get("id") or ""),
        magnitude=_decimal(properties.get("mag")),
        place=str(properties.get("place") or properties.get("title") or ""),
        latitude=_decimal(coordinates[1]) or Decimal(0),
        longitude=_decimal(coordinates[0]) or Decimal(0),
        depth_km=_decimal(coordinates[2]) if len(coordinates) >= 3 else None,
        occurred_at=occurred_at,
        grid_processed_at=(
            _iso(product_properties.get("process-timestamp"))
            or _epoch_ms(product.get("updateTime"))
        ),
        version=(
            str(product_properties["version"])
            if product_properties.get("version")
            else None
        ),
        map_status=(
            str(product_properties["map-status"])
            if product_properties.get("map-status")
            else None
        ),
        declared_max_mmi=_decimal(product_properties.get("maxmmi")),
        declared_max_pga=_decimal(product_properties.get("maxpga")),
        contour_interval=_contour_interval(bands),
        bands=bands,
        contour_url=contour_url,
        pager=_parse_pager(properties.get("products") or {}),
    )
