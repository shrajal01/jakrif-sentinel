import json
import logging
import random
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
from worker.publisher import publisher

logger = logging.getLogger(__name__)

async def process_payment_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """
    Process an incoming RabbitMQ message from the payment queue.
    """
    try:
        # Use explicit ACK/REJECT handling instead of message.process() context manager
        # This gives us fine-grained control to prevent infinite loops (poison pills)
        body = ""
        payment_data = {}
        try:
            body = message.body.decode("utf-8")
            payment_data = json.loads(body)
        except Exception as e:
            logger.error(f"[{message.message_id}] Rejected malformed message: {e}")
            await message.reject(requeue=False)
            return

        payment_id = payment_data.get("payment_id")
        amount = payment_data.get("amount")
        currency = payment_data.get("currency")
        merchant_reference = payment_data.get("merchant_reference")

        if not payment_id:
            logger.error(f"[{message.message_id}] Rejected message missing payment_id: {payment_data}")
            await message.reject(requeue=False)
            return

        logger.info(f"[{payment_id}] Payment Received - Request: {payment_data}")

        async with AsyncSessionLocal() as db:
            try:
                # 1. Update to ENQUEUED
                await update_payment_status_by_uuid(db, payment_id, PaymentStatus.ENQUEUED)
                logger.info(f"[{payment_id}] Enqueued - Status updated in database")

                # 2. Update to PROCESSING
                await update_payment_status_by_uuid(db, payment_id, PaymentStatus.PROCESSING)
                logger.info(f"[{payment_id}] Processing - Contacting Fake Bank")

                # 3. Call Fake Bank
                try:
                    response = await fake_bank_service.process_transaction(
                        amount=amount,
                        currency=currency,
                        reference=merchant_reference
                    )
                    logger.info(f"[{payment_id}] Bank Response - {response}")

                    if response.get("status") == "SUCCESS":
                        await update_payment_status_by_uuid(db, payment_id, PaymentStatus.SUCCESS)
                        logger.info(f"[{payment_id}] Final Status - SUCCESS")
                    else:
                        await update_payment_status_by_uuid(db, payment_id, PaymentStatus.FAILED)
                        logger.info(f"[{payment_id}] Final Status - FAILED (Bank declined)")

                except (FakeBankTimeoutError, FakeBankServerError) as e:
                    logger.warning(f"[{payment_id}] Bank Response - RECOVERABLE ERROR: {e}")
                    
                    retry_count = payment_data.get("retry_count", 0)
                    
                    if retry_count >= 3:
                        logger.warning(f"[{payment_id}] Max retries (3) reached. Failing payment.")
                        await update_payment_status_by_uuid(db, payment_id, PaymentStatus.FAILED)
                        logger.info(f"[{payment_id}] Final Status - FAILED (Max retries reached)")
                    else:
                        payment_data["retry_count"] = retry_count + 1
                        
                        # Exponential backoff with jitter
                        base_delay = 5  # Base delay of 5 seconds
                        delay = (base_delay * (2 ** retry_count)) + random.uniform(0, 2)
                        payment_data["retry_delay"] = delay
                        
                        await publisher.publish_to_queue(
                            settings.PAYMENTS_RETRY_QUEUE_NAME,
                            payment_data
                        )
                        
                        logger.info(f"[{payment_id}] Payment sent to retry queue. Retry {payment_data['retry_count']}/3. Delay: {delay:.2f}s. Final Status - PROCESSING (Retrying)")

                # Acknowledge successful processing (including expected business failures)
                await message.ack()

            except ValueError as e:
                # DB transition failure or UUID not found (invalid state, do not requeue)
                logger.error(f"[{payment_id}] Database/State Error: {e}")
                await message.reject(requeue=False)
                
            except Exception as e:
                # Unexpected database failure (e.g., connection lost)
                logger.error(f"[{payment_id}] Unexpected error during processing: {e}", exc_info=True)
                await message.reject(requeue=False)

    except Exception as e:
        # Ultimate fallback to ensure worker NEVER crashes
        logger.critical(f"Critical error in message handler: {e}", exc_info=True)
        try:
            await message.reject(requeue=False)
        except Exception:
            pass


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

    logger.info(f"Declaring retry queue: {settings.PAYMENTS_RETRY_QUEUE_NAME}")
    await channel.declare_queue(
        settings.PAYMENTS_RETRY_QUEUE_NAME,
        durable=True
    )

    logger.info(f"Declaring dead letter queue: {settings.PAYMENTS_DEAD_LETTER_QUEUE_NAME}")
    await channel.declare_queue(
        settings.PAYMENTS_DEAD_LETTER_QUEUE_NAME,
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
