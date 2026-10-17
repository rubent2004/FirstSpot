"""FastAPI application bootstrap, CORS configuration, routers, and OpenAPI contract."""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings
from app.modules.hazards.infrastructure.router import router as hazards_router
from app.modules.institutions.infrastructure.router import router as institutions_router
from app.modules.places.infrastructure.activity_router import router as activity_router
from app.modules.places.infrastructure.router import router as places_router


class HealthResponse(BaseModel):
    """Typed response contract for service health status."""

    status: str = Field(
        default="ok",
        description="Operational status of the API service.",
    )
    service: str = Field(
        default=settings.app_name,
        description="Human-readable application service name.",
    )
    version: str = Field(
        default="0.1.0",
        description="Semantic version of the backend API.",
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Geospatial prioritization platform for humanitarian response, "
            "civil protection, and healthcare institutions."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get(
        f"{settings.api_v1_prefix}/health",
        response_model=HealthResponse,
        operation_id="getHealthStatus",
        tags=["system"],
        summary="Get API service health status",
    )
    async def get_health_status() -> HealthResponse:
        """Return operational status of the backend service."""
        return HealthResponse(
            status="ok",
            service=settings.app_name,
            version="0.1.0",
        )

    application.include_router(places_router, prefix=settings.api_v1_prefix)
    application.include_router(activity_router, prefix=settings.api_v1_prefix)
    application.include_router(institutions_router, prefix=settings.api_v1_prefix)
    application.include_router(hazards_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()


def export_openapi_schema(output_path: str | Path = "openapi.json") -> Path:
    """Export the OpenAPI 3.1 schema JSON to disk for frontend client generation."""
    target = Path(output_path)
    target.write_text(
        json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    exported = export_openapi_schema()
    print(f"Exported OpenAPI schema to {exported.resolve()}")
