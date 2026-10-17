"""Memory-bounded streaming reader for large ArcGIS GeoJSON exports.

The census cartography ships at full precision: 162 MB for DEGURBA and 164 MB for
the census segments. Parsing either with ``json.load`` materialises the whole
coordinate tree in memory, so features are scanned one at a time instead.

The scanner anchors on the ``"features"`` array and therefore never mistakes the
``crs`` member -- which ArcGIS emits as ``{"type":"name","properties":{...}}`` --
for a feature. A truncated file raises instead of yielding a partial corpus,
because a silently short ingest is indistinguishable from real data loss.
"""

from collections.abc import Iterator
import json
from pathlib import Path
import re
from typing import IO, Any

DEFAULT_BUFFER_SIZE = 1 << 20
"""Read granularity. Large enough to amortise syscalls, small enough to stay bounded."""

MINIMUM_BUFFER_SIZE = 64
"""Floor for the read granularity, so a tiny buffer cannot stall the scanner."""

_FEATURES_KEY = '"features"'
_STRUCTURAL = re.compile(r'["{}]')
_INSIGNIFICANT = " \t\r\n,"


class GeoJsonStreamError(ValueError):
    """Raised when a GeoJSON payload is malformed, truncated, or not a collection."""


class _FeatureScanner:
    """Incremental brace scanner over the ``features`` array of a GeoJSON file."""

    __slots__ = ("_buffer", "_buffer_size", "_handle", "_exhausted", "_position")

    def __init__(self, handle: IO[str], buffer_size: int) -> None:
        self._handle = handle
        self._buffer_size = max(buffer_size, MINIMUM_BUFFER_SIZE)
        self._buffer = ""
        self._position = 0
        self._exhausted = False

    def _read_more(self) -> bool:
        """Append the next chunk to the buffer, returning False at end of file."""
        if self._exhausted:
            return False
        chunk = self._handle.read(self._buffer_size)
        if not chunk:
            self._exhausted = True
            return False
        self._buffer += chunk
        return True

    def _discard_consumed(self) -> None:
        """Drop the already-scanned prefix so buffer growth stays bounded."""
        if self._position:
            self._buffer = self._buffer[self._position :]
            self._position = 0

    def enter_features_array(self) -> None:
        """Advance the cursor just past the opening bracket of ``features``."""
        while True:
            key_index = self._buffer.find(_FEATURES_KEY, self._position)
            if key_index != -1:
                bracket = self._buffer.find("[", key_index + len(_FEATURES_KEY))
                if bracket != -1:
                    self._position = bracket + 1
                    self._discard_consumed()
                    return
            if not self._read_more():
                raise GeoJsonStreamError(
                    "Payload has no 'features' array: not a GeoJSON FeatureCollection"
                )

    def next_feature_text(self) -> str | None:
        """Return the next raw feature object, or None at the end of the array."""
        while True:
            while (
                self._position < len(self._buffer)
                and self._buffer[self._position] in _INSIGNIFICANT
            ):
                self._position += 1
            if self._position < len(self._buffer):
                break
            if not self._read_more():
                raise GeoJsonStreamError(
                    "Unterminated 'features' array: the payload is truncated"
                )

        character = self._buffer[self._position]
        if character == "]":
            self._position += 1
            return None
        if character != "{":
            raise GeoJsonStreamError(
                f"Expected a feature object but found {character!r} "
                f"inside the 'features' array"
            )
        self._discard_consumed()
        return self._scan_object()

    def _scan_object(self) -> str:
        """Scan one balanced JSON object starting at the cursor and return its text."""
        start = self._position
        depth = 0
        index = start
        while True:
            match = _STRUCTURAL.search(self._buffer, index)
            if match is None:
                index = len(self._buffer)
                if not self._read_more():
                    raise GeoJsonStreamError(
                        "Truncated feature: the payload ends inside an object"
                    )
                continue
            character = match.group()
            index = match.end()
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    self._position = index
                    return self._buffer[start:index]
            else:
                index = self._skip_string(index)

    def _skip_string(self, index: int) -> int:
        """Return the index just past a string literal whose opening quote was consumed."""
        while True:
            while index < len(self._buffer):
                character = self._buffer[index]
                if character == "\\":
                    if index + 1 >= len(self._buffer):
                        break
                    index += 2
                    continue
                if character == '"':
                    return index + 1
                index += 1
            if not self._read_more():
                raise GeoJsonStreamError(
                    "Truncated feature: the payload ends inside a string"
                )


def iter_geojson_feature_texts(
    path: Path | str,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
) -> Iterator[str]:
    """Yield each feature of a GeoJSON file as raw JSON text."""
    with Path(path).open("r", encoding="utf-8") as handle:
        scanner = _FeatureScanner(handle, buffer_size)
        scanner.enter_features_array()
        while True:
            feature_text = scanner.next_feature_text()
            if feature_text is None:
                return
            yield feature_text


def iter_geojson_features(
    path: Path | str,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
) -> Iterator[dict[str, Any]]:
    """Yield each feature of a GeoJSON file as a parsed dictionary."""
    for feature_text in iter_geojson_feature_texts(path, buffer_size=buffer_size):
        try:
            yield json.loads(feature_text)
        except json.JSONDecodeError as exc:
            raise GeoJsonStreamError(f"Malformed GeoJSON feature: {exc}") from exc


def count_geojson_features(
    path: Path | str,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
) -> int:
    """Count the features of a GeoJSON file without parsing their geometry."""
    return sum(1 for _ in iter_geojson_feature_texts(path, buffer_size=buffer_size))
