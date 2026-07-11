import json
import logging
import aio_pika

from worker.config import settings
from app.services.fake_bank import (
    fake_bank_service,
    FakeBankTimeoutError,
    FakeBankServerError,
)

logger = logging.getLogger(__name__)

async def process_payment_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """
    Process an incoming RabbitMQ message from the payment queue.
    """
    # Using message.process() automatically ACKs the message when the context manager 
    # exits without exceptions. By catching all exceptions inside, we ensure the 
    # message is ACKed and NOT retried.
    async with message.process():
        logger.info("--- Received Payment Message ---")
        payment_data = {}
        try:
            body = message.body.decode("utf-8")
            payment_data = json.loads(body)
            
            payment_id = payment_data.get("payment_id")
            amount = payment_data.get("amount")
            currency = payment_data.get("currency")
            merchant_reference = payment_data.get("merchant_reference")

            logger.info(f"Payment ID: {payment_id}")
            logger.info(f"Request: {payment_data}")

            # Call Fake Bank asynchronously
            response = await fake_bank_service.process_transaction(
                amount=amount,
                currency=currency,
                reference=merchant_reference
            )
            
            logger.info(f"Response: {response}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message JSON: {e}")
        except FakeBankTimeoutError as e:
            logger.error(f"Fake Bank Timeout for Payment ID {payment_data.get('payment_id')}: {e}")
        except FakeBankServerError as e:
            logger.error(f"Fake Bank Server Error for Payment ID {payment_data.get('payment_id')}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing payment message: {e}", exc_info=True)
            
        logger.info("--- End Payment Message Processing ---")


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
