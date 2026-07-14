import asyncio
import sys
import os
import platform

from worker.consumer import start_consumer
from app.services.redis_service import redis_service
from app.core.logging import configure_structlog, get_logger
from app.core.context import worker_id as worker_id_var

# Configure structured logging before anything else
configure_structlog()
logger = get_logger("worker.main")

# Generate and set a worker ID for process-scoped context
worker_id = f"{platform.node()}-{os.getpid()}"
worker_id_var.set(worker_id)

async def main() -> None:
    logger.info("Initializing worker...")
    connection = None
    try:
        await redis_service.connect()
        connection = await start_consumer()
        logger.info("Worker is running. Press CTRL+C to exit.")
        
        # Continuously wait for messages
        await asyncio.Future()
        
    except asyncio.CancelledError:
        logger.info("Received cancellation signal. Shutting down...")
    except Exception as e:
        logger.error(f"Worker encountered an error: {e}", exc_info=True)
    finally:
        await redis_service.disconnect()
        if connection and not connection.is_closed:
            logger.info("Closing RabbitMQ connection...")
            await connection.close()
            logger.info("RabbitMQ connection closed.")

if __name__ == "__main__":
    # Fix for psycopg async mode on Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Graceful shutdown triggered via KeyboardInterrupt. Exiting...")
