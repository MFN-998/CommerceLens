"""Minimal API foundation. Database and analytics arrive in later phases."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from api.app.config import Settings


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["commercelens-api"] = "commercelens-api"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Load settings when the server starts, with explicit injection for tests."""
    resolved_settings = settings if settings is not None else Settings()
    app = FastAPI(
        title="CommerceLens API",
        version="0.1.0",
        description="Phase 1 foundation. Analytics and data endpoints are not implemented yet.",
    )
    app.state.settings = resolved_settings

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        """Process liveness only; does not claim database or data readiness."""
        return HealthResponse()

    return app
