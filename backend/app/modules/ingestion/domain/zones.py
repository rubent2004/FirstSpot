"""Predefined geographic zones in Latin America for humanitarian prioritization."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PredefinedZone:
    """Immutable definition of a target geographic zone for OSM ingestion."""

    key: str
    name: str
    department: str
    latitude: float
    longitude: float
    default_radius_meters: int
    country: str = "El Salvador"


PREDEFINED_ZONES: dict[str, PredefinedZone] = {
    # El Salvador
    "sonsonate": PredefinedZone(
        key="sonsonate",
        name="Sonsonate",
        department="Sonsonate",
        latitude=13.7222,
        longitude=-89.7236,
        default_radius_meters=10000,
        country="El Salvador",
    ),
    "san_salvador": PredefinedZone(
        key="san_salvador",
        name="San Salvador",
        department="San Salvador",
        latitude=13.6929,
        longitude=-89.2182,
        default_radius_meters=8000,
        country="El Salvador",
    ),
    "santa_ana": PredefinedZone(
        key="santa_ana",
        name="Santa Ana",
        department="Santa Ana",
        latitude=13.9942,
        longitude=-89.5597,
        default_radius_meters=8000,
        country="El Salvador",
    ),
    "san_miguel": PredefinedZone(
        key="san_miguel",
        name="San Miguel",
        department="San Miguel",
        latitude=13.4833,
        longitude=-88.1833,
        default_radius_meters=8000,
        country="El Salvador",
    ),
    "santa_tecla": PredefinedZone(
        key="santa_tecla",
        name="Santa Tecla",
        department="La Libertad",
        latitude=13.6769,
        longitude=-89.2797,
        default_radius_meters=7000,
        country="El Salvador",
    ),
    "acajutla": PredefinedZone(
        key="acajutla",
        name="Acajutla",
        department="Sonsonate",
        latitude=13.5928,
        longitude=-89.8275,
        default_radius_meters=7000,
        country="El Salvador",
    ),

    # Guatemala
    "guatemala_city": PredefinedZone(
        key="guatemala_city",
        name="Ciudad de Guatemala",
        department="Guatemala",
        latitude=14.6349,
        longitude=-90.5069,
        default_radius_meters=10000,
        country="Guatemala",
    ),
    "escuintla": PredefinedZone(
        key="escuintla",
        name="Escuintla",
        department="Escuintla",
        latitude=14.3009,
        longitude=-90.7850,
        default_radius_meters=8000,
        country="Guatemala",
    ),
    "quetzaltenango": PredefinedZone(
        key="quetzaltenango",
        name="Quetzaltenango",
        department="Quetzaltenango",
        latitude=14.8347,
        longitude=-91.5181,
        default_radius_meters=8000,
        country="Guatemala",
    ),

    # Honduras
    "tegucigalpa": PredefinedZone(
        key="tegucigalpa",
        name="Tegucigalpa",
        department="Francisco Morazán",
        latitude=14.0723,
        longitude=-87.1921,
        default_radius_meters=9000,
        country="Honduras",
    ),
    "san_pedro_sula": PredefinedZone(
        key="san_pedro_sula",
        name="San Pedro Sula",
        department="Cortés",
        latitude=15.5000,
        longitude=-88.0333,
        default_radius_meters=9000,
        country="Honduras",
    ),

    # Costa Rica
    "san_jose_cr": PredefinedZone(
        key="san_jose_cr",
        name="San José",
        department="San José",
        latitude=9.9281,
        longitude=-84.0907,
        default_radius_meters=8000,
        country="Costa Rica",
    ),
    "puntarenas": PredefinedZone(
        key="puntarenas",
        name="Puntarenas",
        department="Puntarenas",
        latitude=9.9763,
        longitude=-84.8384,
        default_radius_meters=7000,
        country="Costa Rica",
    ),

    # Colombia
    "bogota": PredefinedZone(
        key="bogota",
        name="Bogotá",
        department="Cundinamarca",
        latitude=4.7110,
        longitude=-74.0721,
        default_radius_meters=10000,
        country="Colombia",
    ),
    "medellin": PredefinedZone(
        key="medellin",
        name="Medellín",
        department="Antioquia",
        latitude=6.2442,
        longitude=-75.5812,
        default_radius_meters=9000,
        country="Colombia",
    ),
    "cali": PredefinedZone(
        key="cali",
        name="Cali",
        department="Valle del Cauca",
        latitude=3.4516,
        longitude=-76.5320,
        default_radius_meters=9000,
        country="Colombia",
    ),

    # Ecuador
    "quito": PredefinedZone(
        key="quito",
        name="Quito",
        department="Pichincha",
        latitude=-0.1807,
        longitude=-78.4678,
        default_radius_meters=10000,
        country="Ecuador",
    ),
    "guayaquil": PredefinedZone(
        key="guayaquil",
        name="Guayaquil",
        department="Guayas",
        latitude=-2.1894,
        longitude=-79.8891,
        default_radius_meters=9000,
        country="Ecuador",
    ),

    # México
    "cdmx": PredefinedZone(
        key="cdmx",
        name="Ciudad de México",
        department="CDMX",
        latitude=19.4326,
        longitude=-99.1332,
        default_radius_meters=10000,
        country="México",
    ),
    "oaxaca": PredefinedZone(
        key="oaxaca",
        name="Oaxaca de Juárez",
        department="Oaxaca",
        latitude=17.0732,
        longitude=-96.7266,
        default_radius_meters=8000,
        country="México",
    ),

    # Perú
    "lima": PredefinedZone(
        key="lima",
        name="Lima",
        department="Lima",
        latitude=-12.0464,
        longitude=-77.0428,
        default_radius_meters=10000,
        country="Perú",
    ),
    "arequipa": PredefinedZone(
        key="arequipa",
        name="Arequipa",
        department="Arequipa",
        latitude=-16.4090,
        longitude=-71.5375,
        default_radius_meters=8000,
        country="Perú",
    ),

    # Chile
    "santiago": PredefinedZone(
        key="santiago",
        name="Santiago",
        department="Región Metropolitana",
        latitude=-33.4489,
        longitude=-70.6693,
        default_radius_meters=10000,
        country="Chile",
    ),
    "valparaiso": PredefinedZone(
        key="valparaiso",
        name="Valparaíso",
        department="Valparaíso",
        latitude=-33.0472,
        longitude=-71.6127,
        default_radius_meters=8000,
        country="Chile",
    ),
}


def get_predefined_zone(zone_key_or_name: str) -> PredefinedZone | None:
    """Resolve a predefined zone by its key or display name (case-insensitive)."""
    normalized = zone_key_or_name.strip().lower().replace(" ", "_")
    if normalized in PREDEFINED_ZONES:
        return PREDEFINED_ZONES[normalized]
    for zone in PREDEFINED_ZONES.values():
        if zone.name.lower() == zone_key_or_name.strip().lower():
            return zone
    return None
