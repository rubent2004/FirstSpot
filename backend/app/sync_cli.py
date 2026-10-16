import asyncio
import sys
from app.core.database import async_session_factory
from app.modules.ingestion.infrastructure.overpass_client import OverpassHttpClient
from app.modules.places.infrastructure.router import SyncZoneRequest, sync_places_from_overpass


async def main(zone_key: str) -> None:
    req = SyncZoneRequest(zone_key=zone_key)
    async with async_session_factory() as session:
        res = await sync_places_from_overpass(
            req,
            session,
            OverpassHttpClient(timeout_seconds=12.0),
        )
        print(
            f"Synced zone={res.zone_name}: {res.synced_places_count} places "
            f"(used_fallback={res.used_fallback}, source={res.source_endpoint})"
        )


if __name__ == "__main__":
    zone = sys.argv[1] if len(sys.argv) > 1 else "sonsonate"
    asyncio.run(main(zone))
