import json
from typing import Any, Dict

import aio_pika
from aio_pika import Message, DeliveryMode

from worker.config import settings
from app.core.logging import get_logger

logger = get_logger("worker.publisher")

class RabbitMQPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        if not self.connection or self.connection.is_closed or not self.exchange:
            try:
                logger.info("Connecting to RabbitMQ...")
                if not self.connection or self.connection.is_closed:
                    self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
                
                if not self.channel or self.channel.is_closed:
                    self.channel = await self.connection.channel()
                
                # Declare exchange
                if not self.exchange:
                    self.exchange = await self.channel.declare_exchange(
                        settings.PAYMENTS_EXCHANGE_NAME, 
                        aio_pika.ExchangeType.DIRECT, 
                        durable=True
                    )
                
                # Declare queue
                queue = await self.channel.declare_queue(
                    settings.PAYMENTS_QUEUE_NAME, 
                    durable=True
                )
                
                # Declare retry queue
                await self.channel.declare_queue(
                    settings.PAYMENTS_RETRY_QUEUE_NAME, 
                    durable=True
                )
                
                # Declare dead letter queue
                await self.channel.declare_queue(
                    settings.PAYMENTS_DEAD_LETTER_QUEUE_NAME, 
                    durable=True
                )
                
                # Bind queue to exchange
                await queue.bind(
                    self.exchange, 
                    routing_key=settings.PAYMENTS_ROUTING_KEY
                )
                logger.info("RabbitMQ connection established and configured.")
            except Exception as e:
                logger.error(f"Error connecting to RabbitMQ: {str(e)}")
                raise

    async def publish(self, routing_key: str, message: Dict[str, Any]):
        try:
            await self.connect()
            message_body = json.dumps(message).encode('utf-8')
            
            msg = Message(
                body=message_body,
                delivery_mode=DeliveryMode.PERSISTENT
            )
            
            logger.debug(f"Publishing message to {routing_key}: {message}")

            assert self.exchange is not None, "Exchange must be initialized before publishing"
            await self.exchange.publish(
                msg,
                routing_key=routing_key
            )
            logger.info("Message published successfully.")
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            raise

    async def publish_to_queue(self, queue_name: str, message: Dict[str, Any]):
        """
        Publish a message directly to a specific queue via the default exchange.
        """
        try:
            await self.connect()
            message_body = json.dumps(message).encode('utf-8')
            
            msg = Message(
                body=message_body,
                delivery_mode=DeliveryMode.PERSISTENT
            )
            
            logger.debug(f"Publishing message directly to queue {queue_name}: {message}")

            assert self.channel is not None, "Channel must be initialized before publishing"
            await self.channel.default_exchange.publish(
                msg,
                routing_key=queue_name
            )
            logger.info(f"Message published to {queue_name} successfully.")
        except Exception as e:
            logger.error(f"Failed to publish message to queue {queue_name}: {str(e)}")
            raise

publisher = RabbitMQPublisher()

async def publish_payment_event(payment_data: Dict[str, Any]):
    """
    Reusable function to publish a payment event to RabbitMQ.
    """
    await publisher.publish(
        routing_key=settings.PAYMENTS_ROUTING_KEY,
        message=payment_data
    )
