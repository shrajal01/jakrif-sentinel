import json
import logging
import aio_pika

from worker.config import settings

logger = logging.getLogger(__name__)

async def process_payment_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """
    Process an incoming RabbitMQ message from the payment queue.
    """
    async with message.process():
        try:
            body = message.body.decode("utf-8")
            payment_data = json.loads(body)
            logger.info(f"Received payment: {json.dumps(payment_data, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message JSON: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing payment message: {e}")

async def start_consumer() -> aio_pika.abc.AbstractRobustConnection:
    """
    Connects to RabbitMQ and starts consuming messages from the payment queue.
    Returns the connection object so it can be gracefully closed on shutdown.
    """
    logger.info("Connecting to RabbitMQ...")
    
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    
    # Set QoS to 1 for fair dispatch
    await channel.set_qos(prefetch_count=1)
    
    queue = await channel.declare_queue(
        settings.PAYMENTS_QUEUE_NAME,
        durable=True
    )
    
    logger.info(f"Waiting for messages in queue: {settings.PAYMENTS_QUEUE_NAME}")
    
    await queue.consume(process_payment_message)
    return connection
