"""
API router factory for creating and registering all API routes.
"""

from fastapi import APIRouter

from .entities import get_entity_routers


def create_api_router() -> APIRouter:
    """
    Create and return the main API router with all routes registered.

    Returns:
        APIRouter: The configured API router with all subrouters included
    """
    # Create main API router
    api_router = APIRouter(prefix="/api")

    # Include all subrouters from the entities registry
    for router in get_entity_routers():
        api_router.include_router(router)

    return api_router
