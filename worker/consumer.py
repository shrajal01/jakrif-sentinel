import json
import logging
import aio_pika

from worker.config import settings
from app.services.fake_bank import (
    fake_bank_service,
    FakeBankTimeoutError,
    FakeBankServerError,
)
from app.database.session import AsyncSessionLocal
from app.services.payment_service import update_payment_status_by_uuid
from app.models.payment import PaymentStatus

logger = logging.getLogger(__name__)

async def process_payment_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """
    Process an incoming RabbitMQ message from the payment queue.
    """
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

            async with AsyncSessionLocal() as db:
                # 1. Update to ENQUEUED
                await update_payment_status_by_uuid(db, payment_id, PaymentStatus.ENQUEUED)
                logger.info(f"Payment {payment_id} status updated to ENQUEUED")

                # 2. Update to PROCESSING
                await update_payment_status_by_uuid(db, payment_id, PaymentStatus.PROCESSING)
                logger.info(f"Payment {payment_id} status updated to PROCESSING")

                # 3. Call Fake Bank
                try:
                    response = await fake_bank_service.process_transaction(
                        amount=amount,
                        currency=currency,
                        reference=merchant_reference
                    )
                    logger.info(f"Response: {response}")

                    if response.get("status") == "SUCCESS":
                        await update_payment_status_by_uuid(db, payment_id, PaymentStatus.SUCCESS)
                        logger.info(f"Payment {payment_id} status updated to SUCCESS")
                    else:
                        await update_payment_status_by_uuid(db, payment_id, PaymentStatus.FAILED)
                        logger.info(f"Payment {payment_id} status updated to FAILED")

                except (FakeBankTimeoutError, FakeBankServerError) as e:
                    logger.error(f"Fake Bank Error for Payment ID {payment_id}: {e}")
                    await update_payment_status_by_uuid(db, payment_id, PaymentStatus.FAILED)
                    logger.info(f"Payment {payment_id} status updated to FAILED due to external error")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message JSON: {e}")
        except ValueError as e:
            logger.error(f"Status transition or DB error for Payment ID {payment_data.get('payment_id')}: {e}")
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
