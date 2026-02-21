"""
Application entry point.

Responsible for:
- Initializing the FastAPI application.
- Registering API routes.
- Managing application lifespan events (startup/shutdown).

No business logic should live in this module.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router
from infra.http_client import close_client


# Application lifespan handler.
# Ensures proper resource cleanup during shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application startup hook (no-op for this service).
    yield
    # Gracefully close shared HTTP client on shutdown.
    await close_client()


# FastAPI application instance with custom lifespan management.
app = FastAPI(
    title="Notification Service (AI Technical Test)",
    lifespan=lifespan,
)

# Register API routes.
app.include_router(router)