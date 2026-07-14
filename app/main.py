from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.api.auth import router as auth_router
from app.api.payments import router as payments_router
from app.api.dashboard import router as dashboard_router
from app.core.config import settings
from app.core.logging import configure_structlog, get_logger
from app.core.middleware import RequestContextMiddleware
from app.database.session import engine
from app.services.redis_service import redis_service

# Configure structured logging before anything else
configure_structlog()
logger = get_logger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Validates database connection at startup.
    Cleans up resources at shutdown.
    """
    try:
        # Verify database connection using SQLAlchemy 2.x style
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Successfully connected to the database.")
            
        # Connect to Redis
        await redis_service.connect()
    except SQLAlchemyError as e:
        logger.error("Database connection failed", error=str(e))
        raise
    except Exception as e:
        logger.error("Unexpected startup error", error=str(e), exc_info=True)
        raise

    yield  # Application runs during this period

    # Gracefully dispose of all database connections
    logger.info("Shutting down application...")
    engine.dispose()
    await redis_service.disconnect()
    logger.info("Database connections disposed.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A Fault-Tolerant Payment Reliability Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Add structured logging middleware
app.add_middleware(RequestContextMiddleware)

# Mount the router
app.include_router(api_router)
app.include_router(auth_router)
app.include_router(payments_router)
app.include_router(dashboard_router)

@app.get("/health", tags=["Health"])
def health_check():
    """
    Backend is Running .
    """
    return {"status": "healthy"}
