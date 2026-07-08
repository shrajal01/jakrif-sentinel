from fastapi import APIRouter

# The root API router that aggregates other routers
api_router = APIRouter()

# Example usage for future:
# api_router.include_router(v1_router, prefix="/v1")
