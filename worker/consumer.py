import logging
import aio_pika

from worker.config import settings

logger = logging.getLogger(__name__)

async def process_payment_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """
    Process an incoming RabbitMQ message from the payment queue.
    """
    async with message.process():
        logger.info("--- Received message ---")
        logger.info(f"Delivery tag: {message.delivery_tag}")
        try:
            body = message.body.decode("utf-8")
            logger.info(f"Message body: {body}")
        except Exception as e:
            logger.error(f"Failed to decode message body: {e}")
        logger.info("------------------------")

async def start_consumer() -> aio_pika.abc.AbstractRobustConnection:
    """
    Connects to RabbitMQ, sets up the exchange/queue/binding, and starts consuming.
    """
    logger.info("Connecting to RabbitMQ...")
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()

    # Set QoS for fair dispatch
    await channel.set_qos(prefetch_count=1)

    logger.info(f"Declaring exchange: {settings.PAYMENTS_EXCHANGE_NAME}")
    exchange = await channel.declare_exchange(
        settings.PAYMENTS_EXCHANGE_NAME,
        aio_pika.ExchangeType.DIRECT,
        durable=True
    )

    logger.info(f"Declaring queue: {settings.PAYMENTS_QUEUE_NAME}")
    queue = await channel.declare_queue(
        settings.PAYMENTS_QUEUE_NAME,
        durable=True
    )

    logger.info(f"Binding queue to exchange with routing key: {settings.PAYMENTS_ROUTING_KEY}")
    await queue.bind(
        exchange,
        routing_key=settings.PAYMENTS_ROUTING_KEY
    )

    logger.info("Starting to consume messages...")
    await queue.consume(process_payment_message)
    
    return connection
