"""Asynchronous USGS adapter for the event catalogue and ShakeMap releases.

No API key is required. Tests never reach this module's network paths: they run
against recorded fixtures, and a live call belongs in a verification run.
"""

from typing import Protocol

import httpx

from app.modules.hazards.domain.shakemap import (
    USGS_EVENT_QUERY_URL,
    EarthquakeEventSummary,
    ShakeMapError,
    ShakeMapRelease,
    mmi_contour_url,
    parse_event_summaries,
    parse_shakemap_release,
)

USER_AGENT = "FirstSpot/0.2 (Humanitarian Response El Salvador)"

EL_SALVADOR_BBOX = {
    "minlatitude": 12.8,
    "maxlatitude": 14.6,
    "minlongitude": -90.2,
    "maxlongitude": -87.6,
}
"""Search box around El Salvador used by the event catalogue."""


class ShakeMapProviderError(RuntimeError):
    """Raised when USGS cannot be reached or answers unusably."""


class ShakeMapProviderPort(Protocol):
    """Outbound port so routes can be tested without the network."""

    async def list_events(
        self, min_magnitude: float, limit: int, start_time: str | None
    ) -> tuple[EarthquakeEventSummary, ...]: ...

    async def fetch_release(self, event_id: str) -> ShakeMapRelease: ...


class UsgsShakeMapClient:
    """Live USGS FDSN / ShakeMap client."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    async def list_events(
        self, min_magnitude: float = 4.0, limit: int = 50, start_time: str | None = None
    ) -> tuple[EarthquakeEventSummary, ...]:
        params: dict[str, str | float | int] = {
            "format": "geojson",
            "minmagnitude": min_magnitude,
            "orderby": "time",
            "limit": limit,
            **EL_SALVADOR_BBOX,
        }
        if start_time:
            params["starttime"] = start_time
        try:
            async with self._client() as client:
                response = await client.get(USGS_EVENT_QUERY_URL, params=params)
                response.raise_for_status()
                return parse_event_summaries(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise ShakeMapProviderError(f"USGS event query failed: {exc}") from exc

    async def fetch_release(self, event_id: str) -> ShakeMapRelease:
        try:
            async with self._client() as client:
                detail = await client.get(
                    USGS_EVENT_QUERY_URL,
                    params={"eventid": event_id, "format": "geojson"},
                )
                detail.raise_for_status()
                detail_payload = detail.json()
                contours = await client.get(mmi_contour_url(detail_payload))
                contours.raise_for_status()
                return parse_shakemap_release(detail_payload, contours.json())
        except ShakeMapError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ShakeMapProviderError(
                f"USGS ShakeMap fetch for {event_id} failed: {exc}"
            ) from exc
