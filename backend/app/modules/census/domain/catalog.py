"""Declarative catalogue of the CPV 2024 ArcGIS layers consumed by this service.

``poblacion.bcr.gob.sv`` is an ArcGIS Hub site, not a download page. The data is
reached through the public ArcGIS REST API of organization ``bcrsv``
(orgId ``xSn1Pefr3M9zkw7Z``), which exposes 348 Feature Services and requires no
token. Every entry below was resolved by matching the layer's exact row count and
field names against the already-downloaded file, so the local corpus is fully
regenerable.

Two traps are encoded here rather than rediscovered:

* ``maxRecordCount`` is 2,000 on every layer. A larger ``resultRecordCount`` is
  silently truncated and the response carries ``exceededTransferLimit: true``,
  so paging is mandatory for the segment and DEGURBA layers.
* Services bundle unrelated themes. The census segment layer is id **174** of
  ``Segmentos_2024_DAC``, and the three disability levels are ids 4, 5 and 6 of
  a single ``Capas_discapacidad`` service. Matching on service title alone picks
  the wrong layer.
"""

from dataclasses import dataclass
from urllib.parse import quote

ARCGIS_ORG_ID = "xSn1Pefr3M9zkw7Z"
"""ArcGIS Online organization id of the Banco Central de Reserva de El Salvador."""

ARCGIS_ORG_SLUG = "bcrsv"
"""Human-readable organization slug, as used by the ArcGIS Hub site."""

ARCGIS_SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"
"""Item search endpoint used to enumerate the organization's Feature Services."""

ARCGIS_SERVICES_ROOT = (
    f"https://services8.arcgis.com/{ARCGIS_ORG_ID}/arcgis/rest/services"
)
"""Base URL of the organization's hosted Feature Services."""

ARCGIS_MAX_RECORD_COUNT = 2000
"""Server-enforced page size; requesting more is silently truncated."""

OUTPUT_SPATIAL_REFERENCE = "4326"
"""Export SRID. Native references include an inline-WKT Lambert SIRGAS-ES2007
that carries no EPSG code, so an explicit ``outSR`` is required."""


@dataclass(frozen=True, slots=True)
class CensusLayer:
    """One ArcGIS layer and the local file it regenerates."""

    filename: str
    service_name: str
    layer_id: int
    expected_feature_count: int
    title: str
    description: str
    order_by_field: str = "OBJECTID"
    output_format: str = "geojson"
    page_size: int = ARCGIS_MAX_RECORD_COUNT

    @property
    def service_url(self) -> str:
        """Return the FeatureServer URL, percent-encoding non-ASCII service names."""
        return f"{ARCGIS_SERVICES_ROOT}/{quote(self.service_name)}/FeatureServer"

    @property
    def query_url(self) -> str:
        """Return the layer query endpoint."""
        return f"{self.service_url}/{self.layer_id}/query"

    def build_query(
        self,
        offset: int = 0,
        page_size: int | None = None,
    ) -> tuple[str, dict[str, str]]:
        """Build one paged export request for this layer."""
        effective_page_size = min(
            page_size or self.page_size, ARCGIS_MAX_RECORD_COUNT
        )
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": OUTPUT_SPATIAL_REFERENCE,
            "returnGeometry": "true",
            "orderByFields": self.order_by_field,
            "resultOffset": str(offset),
            "resultRecordCount": str(effective_page_size),
            "f": self.output_format,
        }
        return self.query_url, params

    def build_count_query(self) -> tuple[str, dict[str, str]]:
        """Build the exact row-count request used to assert a layer before export."""
        return self.query_url, {
            "where": "1=1",
            "returnCountOnly": "true",
            "f": "json",
        }


CENSUS_LAYERS: tuple[CensusLayer, ...] = (
    # --- Official CNR SIRGAS cartography: the unified administrative hierarchy ---
    CensusLayer(
        filename="limites_departamentos_cnr_sirgas.geojson",
        service_name="LimitesFiltro",
        layer_id=0,
        expected_feature_count=15,
        title="TEG Limites filtro",
        description="Department boundaries (CNR SIRGAS): 14 departments + 1 national rollup.",
    ),
    CensusLayer(
        filename="limites_municipios_cnr_sirgas.geojson",
        service_name="LimitesFiltro",
        layer_id=1,
        expected_feature_count=59,
        title="TEG Limites filtro",
        description="Municipality boundaries: 44 municipalities + 14 'AAA' rollups + 1 national.",
    ),
    CensusLayer(
        filename="limites_distritos_cnr_sirgas.geojson",
        service_name="LimitesFiltro",
        layer_id=2,
        expected_feature_count=307,
        title="TEG Limites filtro",
        description="District boundaries: 262 districts + 44 'AAA' rollups + 1 national.",
    ),
    # --- Fine-grain analysis unit: DEGURBA sub-district polygons ---
    CensusLayer(
        filename="degurba_densidad.geojson",
        service_name="DEGURBA",
        layer_id=0,
        expected_feature_count=1345,
        title="DEGURBA_conDensidad",
        description=(
            "Degree of urbanisation with density: 902 polygons at Nivel 2 "
            "(the analysis unit) and 443 at Nivel 1. Both levels total 5,922,921 people."
        ),
    ),
    # --- Geometry-only context ---
    CensusLayer(
        filename="segmentos_censales_2024.geojson",
        service_name="Segmentos_2024_DAC",
        layer_id=174,
        expected_feature_count=10291,
        title="Segmentos_2024_DAC",
        description=(
            "Census segments: 10,290 polygons + 1 national rollup. Geometry only, "
            "zero population attributes. Context, never a population join target."
        ),
    ),
    # --- Population by age and sex, three levels ---
    CensusLayer(
        filename="departamentos_poblacion_edad_sexo.geojson",
        service_name="Departamento_TPC",
        layer_id=0,
        expected_feature_count=17,
        title="Mapa Discapacidad - Poblacion por departamentos - Nacional",
        description=(
            "Population by age and sex per department: 14 departments, the 'Otros' "
            "row, and 2 null-code duplicate rows. Uses the plural Hombres/Mujeres."
        ),
    ),
    CensusLayer(
        filename="municipios_poblacion_edad_sexo.geojson",
        service_name="MunicipiosCNR__TPC",
        layer_id=0,
        expected_feature_count=45,
        title="MunicipiosCNR TPC",
        description=(
            "Population by age and sex per municipality: 44 municipalities + 'RRAA'. "
            "Carries the same defective Total_Personas column as the district layer."
        ),
    ),
    CensusLayer(
        filename="distritos_poblacion_edad_sexo.geojson",
        service_name="Distritos_TPC",
        layer_id=0,
        expected_feature_count=263,
        title="Distritos TPC",
        description=(
            "Population by age and sex per district: 262 districts + 'RRAA'. "
            "Total_Personas is defective here; derive from Hombre + Mujer."
        ),
    ),
    # --- Disability, three levels ---
    CensusLayer(
        filename="discapacidad_departamentos.geojson",
        service_name="Capas_discapacidad",
        layer_id=4,
        expected_feature_count=14,
        title="TEG - Dificultad o Limitante - Capas",
        description="Persons with a disability per department. National total 281,463.",
    ),
    CensusLayer(
        filename="discapacidad_municipios.geojson",
        service_name="Capas_discapacidad",
        layer_id=5,
        expected_feature_count=44,
        title="TEG - Dificultad o Limitante - Capas",
        description="Persons with a disability per municipality. National total 281,463.",
    ),
    CensusLayer(
        filename="discapacidad_distritos.geojson",
        service_name="Capas_discapacidad",
        layer_id=6,
        expected_feature_count=262,
        title="TEG - Dificultad o Limitante - Capas",
        description="Persons with a disability per district. National total 281,463.",
    ),
    # --- Dwellings and structures, long format across three levels ---
    CensusLayer(
        filename="estructuras_distritos.geojson",
        service_name="Estructuras_capas_mapa_simple",
        layer_id=0,
        expected_feature_count=334,
        title="TEG Estructuras capas simple",
        description=(
            "Structure counts in long format: 262 district rows, 44 municipality "
            "rows and 28 department rows in one layer."
        ),
    ),
    CensusLayer(
        filename="viviendas_particulares_distritos.geojson",
        service_name="Viviendas_particulares_capa_mapa_simple",
        layer_id=0,
        expected_feature_count=334,
        title="TEG Viviendas particulares capa simple",
        description=(
            "Private dwelling counts in long format: 262 district rows, 44 "
            "municipality rows and 28 department rows in one layer."
        ),
    ),
    # --- Attribute tables (no geometry) ---
    CensusLayer(
        filename="tabla_discapacidad_por_tipo_distrito.csv",
        service_name="Tabla_discapacidad",
        layer_id=0,
        expected_feature_count=2247,
        title="TEG Dificultad o Limitante - Tabla para el grafico",
        description="Disability by type per district: 7 labelled difficulty categories.",
        output_format="json",
    ),
    CensusLayer(
        filename="tabla_poblacion_edad_sexo_distrito.csv",
        service_name="tabla_población",
        layer_id=0,
        expected_feature_count=12880,
        title="Tabla poblacion",
        description="Population pyramid source per district; the Poblacion column is signed for chart use.",
        order_by_field="FID",
        output_format="json",
    ),
    CensusLayer(
        filename="tabla_parentesco_hogar_distrito.csv",
        service_name="Parentesco_2nd",
        layer_id=0,
        expected_feature_count=33705,
        title="Parentesco 2nd",
        description=(
            "Household relationship by household type per district: 15 relationship "
            "categories across 7 household types, with 'AAA' rollup rows."
        ),
        output_format="json",
    ),
)

_LAYERS_BY_FILENAME: dict[str, CensusLayer] = {
    layer.filename: layer for layer in CENSUS_LAYERS
}


def layer_by_filename(filename: str) -> CensusLayer:
    """Resolve a catalogue entry from its local filename."""
    try:
        return _LAYERS_BY_FILENAME[filename]
    except KeyError as exc:
        raise KeyError(
            f"{filename!r} is not a declared census layer; "
            f"known layers: {sorted(_LAYERS_BY_FILENAME)}"
        ) from exc


def geojson_layers() -> tuple[CensusLayer, ...]:
    """Return only the catalogue entries stored as GeoJSON feature collections."""
    return tuple(
        layer for layer in CENSUS_LAYERS if layer.filename.endswith(".geojson")
    )
