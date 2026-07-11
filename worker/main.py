import asyncio
import logging
import sys

from worker.consumer import start_consumer

# Configure basic logging for the worker process
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main() -> None:
    """
    Main entrypoint for the RabbitMQ consumer worker.
    """
    logger.info("Initializing worker application...")
    connection = None
    try:
        connection = await start_consumer()
        
        logger.info("Worker successfully started. Press CTRL+C to exit.")
        # Infinite consume loop - await a Future that never resolves
        await asyncio.Future()
        
    except asyncio.CancelledError:
        logger.info("Worker shutting down gracefully (CancelledError)...")
    except Exception as e:
        logger.error(f"Worker encountered an unexpected error: {e}", exc_info=True)
    finally:
        if connection and not connection.is_closed:
            logger.info("Closing RabbitMQ connection...")
            await connection.close()
            logger.info("RabbitMQ connection closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Worker exiting gracefully...")
