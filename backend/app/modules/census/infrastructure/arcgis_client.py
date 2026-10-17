"""Asynchronous ArcGIS REST adapter for the public BCR/ONEC census services.

``poblacion.bcr.gob.sv`` is an ArcGIS Hub front end. The data behind it is reached
through the organization's public REST API, which needs no token and supports
server-side pagination and GeoJSON output.

Two behaviours of this particular deployment shape the adapter:

* ``maxRecordCount`` is 2,000. A larger ``resultRecordCount`` is silently
  truncated and the response sets ``exceededTransferLimit``, so a request that
  looks successful can still be short. Every page is therefore checked.
* ArcGIS reports application errors with HTTP 200 and an ``error`` member, so a
  non-raising response is not proof of success.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
import json
from typing import Any

import httpx

from app.modules.census.domain.catalog import (
    ARCGIS_ORG_ID,
    ARCGIS_SEARCH_URL,
    CensusLayer,
)

USER_AGENT_HEADER = "FirstSpot/0.1 (Humanitarian Response El Salvador)"
"""Identifies this client to the host, as courtesy requires for public APIs."""

DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_MAX_RETRIES = 4
DEFAULT_BACKOFF_SECONDS = 2.0
SEARCH_PAGE_SIZE = 100


class ArcGisQueryError(RuntimeError):
    """Raised when an ArcGIS request fails or returns an application error."""


@dataclass(frozen=True, slots=True)
class ArcGisPage:
    """One page of an ArcGIS layer export."""

    offset: int
    body: str
    feature_count: int
    exceeded_transfer_limit: bool


class ArcGisFeatureServiceClient:
    """Minimal async client for querying public ArcGIS Feature Services."""

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ArcGisFeatureServiceClient":
        """Open the underlying HTTP connection pool."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=15.0),
            headers={"User-Agent": USER_AGENT_HEADER, "Accept": "application/json"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close the underlying HTTP connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _http(self) -> httpx.AsyncClient:
        """Return the active HTTP client, requiring the context manager."""
        if self._client is None:
            raise ArcGisQueryError(
                "ArcGisFeatureServiceClient must be used as an async context manager"
            )
        return self._client

    async def _get_text(self, url: str, params: dict[str, str]) -> str:
        """Perform one GET with bounded retries and exponential backoff."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await self._http.get(url, params=params)
                if response.status_code >= 500:
                    raise ArcGisQueryError(
                        f"{url} returned HTTP {response.status_code}"
                    )
                response.raise_for_status()
                body = response.text
                _raise_for_application_error(url, body)
                return body
            except (httpx.HTTPError, ArcGisQueryError) as exc:
                last_error = exc
                if attempt == self.max_retries - 1:
                    break
                await asyncio.sleep(self.backoff_seconds * (2**attempt))
        raise ArcGisQueryError(
            f"ArcGIS request to {url} failed after {self.max_retries} attempts: "
            f"{last_error}"
        ) from last_error

    async def count_features(self, layer: CensusLayer) -> int:
        """Return the server-reported exact row count of a layer."""
        url, params = layer.build_count_query()
        payload = json.loads(await self._get_text(url, params))
        count = payload.get("count")
        if not isinstance(count, int):
            raise ArcGisQueryError(
                f"{layer.filename}: ArcGIS did not report a row count: {payload}"
            )
        return count

    async def fetch_page(
        self,
        layer: CensusLayer,
        offset: int,
        page_size: int | None = None,
    ) -> ArcGisPage:
        """Fetch one page of a layer export, in the layer's declared format."""
        url, params = layer.build_query(offset=offset, page_size=page_size)
        body = await self._get_text(url, params)
        payload = json.loads(body)
        features = payload.get("features")
        if not isinstance(features, list):
            raise ArcGisQueryError(
                f"{layer.filename}: page at offset {offset} has no features array"
            )
        return ArcGisPage(
            offset=offset,
            body=body,
            feature_count=len(features),
            exceeded_transfer_limit=bool(payload.get("exceededTransferLimit")),
        )

    async def iter_pages(
        self,
        layer: CensusLayer,
        total_features: int,
        start_offset: int = 0,
        page_size: int | None = None,
    ) -> AsyncIterator[ArcGisPage]:
        """Yield successive pages until the layer's full row count is covered."""
        effective_page_size = min(
            page_size or layer.page_size, layer.page_size
        )
        offset = start_offset
        while offset < total_features:
            page = await self.fetch_page(
                layer, offset=offset, page_size=effective_page_size
            )
            if page.feature_count == 0:
                raise ArcGisQueryError(
                    f"{layer.filename}: empty page at offset {offset} while "
                    f"{total_features - offset} rows were still expected"
                )
            yield page
            offset += page.feature_count

    async def search_feature_services(
        self,
        org_id: str = ARCGIS_ORG_ID,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Enumerate the organization's public Feature Services, for auditing."""
        items: list[dict[str, Any]] = []
        start = 1
        while True:
            body = await self._get_text(
                ARCGIS_SEARCH_URL,
                {
                    "q": f'orgid:{org_id} AND type:"Feature Service"',
                    "f": "json",
                    "num": str(SEARCH_PAGE_SIZE),
                    "start": str(start),
                },
            )
            payload = json.loads(body)
            items.extend(payload.get("results") or [])
            next_start = payload.get("nextStart", -1)
            if limit is not None and len(items) >= limit:
                return items[:limit]
            if not isinstance(next_start, int) or next_start <= 0:
                return items
            start = next_start


def _raise_for_application_error(url: str, body: str) -> None:
    """Detect an ArcGIS error returned with an HTTP 200 status."""
    stripped = body.lstrip()
    if not stripped.startswith("{") or '"error"' not in stripped[:4096]:
        return
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return
    error = payload.get("error")
    if isinstance(error, dict):
        raise ArcGisQueryError(
            f"{url} returned an ArcGIS error: "
            f"{error.get('code')} {error.get('message')} "
            f"{error.get('details')}"
        )
