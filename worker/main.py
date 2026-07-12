import asyncio
import logging
import sys

from worker.consumer import start_consumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main() -> None:
    logger.info("Initializing worker...")
    connection = None
    try:
        connection = await start_consumer()
        logger.info("Worker is running. Press CTRL+C to exit.")
        
        # Continuously wait for messages
        await asyncio.Future()
        
    except asyncio.CancelledError:
        logger.info("Received cancellation signal. Shutting down...")
    except Exception as e:
        logger.error(f"Worker encountered an error: {e}", exc_info=True)
    finally:
        if connection and not connection.is_closed:
            logger.info("Closing RabbitMQ connection...")
            await connection.close()
            logger.info("RabbitMQ connection closed.")

if __name__ == "__main__":
    # Fix for psycopg async mode on Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Graceful shutdown triggered via KeyboardInterrupt. Exiting...")
