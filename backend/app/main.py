"""FastAPI application bootstrap, CORS configuration, and health contract."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import settings


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

    return application


app = create_app()
