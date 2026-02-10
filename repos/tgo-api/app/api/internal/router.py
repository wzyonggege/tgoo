"""Internal services router.

This router includes all internal endpoints that do not require authentication.
These endpoints are designed for inter-service communication within the internal network.
"""

from fastapi import APIRouter

from app.api.internal.endpoints import users

internal_router = APIRouter()

# Internal users endpoint
internal_router.include_router(
    users.router,
    prefix="/users",
    tags=["Internal Users"]
)
