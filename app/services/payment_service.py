import asyncio
import uuid
import json
from datetime import datetime
from typing import Optional, List, Tuple

from fastapi import HTTPException, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentCreate
from worker.publisher import publish_payment_event
from app.services.redis_service import redis_service
from app.core.logging import get_logger
from app.core.context import payment_id as payment_id_var

logger = get_logger("service.payment")


async def create_payment(
    db: AsyncSession,
    payment_in: PaymentCreate,
    idempotency_key: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Payment:
    """
    Create a new payment record.
    Generates a UUID automatically and defaults status to CREATED.
    Includes correlation_id in the RabbitMQ message for end-to-end tracing.
    """
    def deserialize_payment(cached_str: str) -> Payment:
        data = json.loads(cached_str)
        from decimal import Decimal
        return Payment(
            id=data.get("id"),
            payment_id=uuid.UUID(data.get("payment_id")),
            amount=Decimal(str(data.get("amount"))),
            currency=data.get("currency"),
            status=PaymentStatus(data.get("status")),
            merchant_reference=data.get("merchant_reference"),
            description=data.get("description"),
            created_at=datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data.get("updated_at")) if data.get("updated_at") else None,
        )

    redis_key = None
    lock_key = None
    redis_available = True
    
    if idempotency_key:
        redis_key = f"idempotency:payments:{idempotency_key}"
        lock_key = f"idempotency:payments:lock:{idempotency_key}"
        
        try:
            # 1. Check if we already processed this exact request
            cached = await redis_service.get(redis_key)
            if cached:
                logger.info("Idempotency HIT. Duplicate prevented.", idempotency_key=idempotency_key)
                return deserialize_payment(cached)
            
            logger.info("Idempotency MISS. Proceeding to acquire lock.", idempotency_key=idempotency_key)
            
            # 2. Acquire a short-lived lock to prevent race conditions during concurrent identical requests
            lock_acquired = await redis_service.set_if_not_exists(lock_key, "locked", expire_seconds=30)
            
            if lock_acquired:
                logger.info("Lock acquired.", idempotency_key=idempotency_key)
            else:
                # Lock exists: Another identical request is currently processing. Wait briefly to see if it finishes.
                logger.info("Idempotency lock exists. Waiting briefly...", idempotency_key=idempotency_key)
                await asyncio.sleep(0.5)
                
                # 3. Check cache one last time after waiting
                cached = await redis_service.get(redis_key)
                if cached:
                    logger.info("Idempotency HIT after wait. Duplicate prevented.", idempotency_key=idempotency_key)
                    return deserialize_payment(cached)
                else:
                    logger.warning("Idempotency lock conflict. Returning 409.", idempotency_key=idempotency_key)
                    raise HTTPException(
                        status_code=http_status.HTTP_409_CONFLICT,
                        detail="A request with this Idempotency-Key is currently being processed."
                    )
        except HTTPException:
            # Re-raise HTTP exceptions so we don't accidentally swallow the 409 Conflict
            raise
        except Exception as e:
            # Gracefully handle Redis failures. We log the error but allow processing to continue normally.
            logger.warning("Redis unavailable during idempotency check. Proceeding without idempotency.", error=str(e))
            redis_available = False
            lock_key = None
            redis_key = None

    try:
        payment = Payment(
            payment_id=uuid.uuid4(),
            amount=payment_in.amount,
            currency=payment_in.currency,
            status=PaymentStatus.CREATED,
            merchant_reference=payment_in.merchant_reference,
            description=payment_in.description
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        # Set payment_id context for downstream logs
        payment_id_var.set(str(payment.payment_id))

        logger.info("Payment created", status=payment.status.value, amount=float(payment.amount), currency=payment.currency)

        try:
            message_payload = {
                "payment_id": str(payment.payment_id),
                "amount": float(payment.amount),
                "currency": payment.currency,
                "merchant_reference": payment.merchant_reference,
            }
            # Propagate correlation_id through the message payload for worker tracing
            if correlation_id:
                message_payload["correlation_id"] = correlation_id

            await publish_payment_event(message_payload)
            logger.info("Payment event published to RabbitMQ")
        except Exception as e:
            logger.error("Failed to publish payment event", error=str(e))

        # 4. Store the successful response in Redis
        if redis_key and redis_available:
            try:
                data_to_cache = {
                    "id": payment.id,
                    "payment_id": str(payment.payment_id),
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "status": payment.status.value,
                    "merchant_reference": payment.merchant_reference,
                    "description": payment.description,
                    "created_at": payment.created_at.isoformat() if payment.created_at else None,
                    "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
                }
                await redis_service.set(redis_key, json.dumps(data_to_cache), expire_seconds=86400)
                logger.info("Cached idempotency response", idempotency_key=idempotency_key)
            except Exception as e:
                logger.warning("Failed to cache response in Redis", error=str(e))

        return payment

    finally:
        # 5. Ensure the lock is released so future retries aren't blocked if processing fails
        if lock_key and redis_available:
            try:
                await redis_service.delete(lock_key)
                logger.info("Lock released.", idempotency_key=idempotency_key)
            except Exception as e:
                logger.warning("Failed to release Redis lock", error=str(e))


async def get_payment(db: AsyncSession, payment_id: int) -> Optional[Payment]:
    """
    Retrieve a payment by its internal ID.
    """
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()


async def get_payment_by_uuid(db: AsyncSession, payment_uuid: uuid.UUID | str) -> Optional[Payment]:
    """
    Retrieve a payment by its external UUID.
    """
    if isinstance(payment_uuid, str):
        payment_uuid = uuid.UUID(payment_uuid)
    result = await db.execute(select(Payment).where(Payment.payment_id == payment_uuid))
    return result.scalar_one_or_none()


async def list_payments(db: AsyncSession, skip: int = 0, limit: int = 100) -> Tuple[List[Payment], int]:
    """
    Retrieve a paginated list of payments along with the total count.
    """
    result = await db.execute(select(Payment).offset(skip).limit(limit))
    items = list(result.scalars().all())
    
    total_result = await db.execute(select(func.count(Payment.id)))
    total = total_result.scalar() or 0
    
    return items, total


ALLOWED_TRANSITIONS = {
    PaymentStatus.CREATED: {PaymentStatus.ENQUEUED},
    PaymentStatus.ENQUEUED: {PaymentStatus.PROCESSING},
    PaymentStatus.PROCESSING: {PaymentStatus.SUCCESS, PaymentStatus.FAILED},
    PaymentStatus.SUCCESS: set(),
    PaymentStatus.FAILED: set(),
}


async def update_payment_status(db: AsyncSession, payment_id: int, status: PaymentStatus) -> Payment:
    """
    Update the status of an existing payment.
    Validates payment existence and allowed state transitions before updating.
    """
    payment = await get_payment(db, payment_id)
    if not payment:
        raise ValueError(f"Payment with id {payment_id} does not exist.")
        
    allowed_next_states = ALLOWED_TRANSITIONS.get(payment.status, set())
    if status not in allowed_next_states:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition from {payment.status.value} to {status.value}"
        )
        
    payment.status = status
    await db.commit()
    await db.refresh(payment)
    return payment


async def update_payment_status_by_uuid(db: AsyncSession, payment_uuid: uuid.UUID | str, status: PaymentStatus) -> Payment:
    """
    Update the status of an existing payment using UUID.
    """
    payment = await get_payment_by_uuid(db, payment_uuid)
    if not payment:
        raise ValueError(f"Payment with uuid {payment_uuid} does not exist.")
        
    allowed_next_states = ALLOWED_TRANSITIONS.get(payment.status, set())
    if status not in allowed_next_states:
        raise ValueError(
            f"Invalid state transition from {payment.status.value} to {status.value}"
        )
        
    payment.status = status
    await db.commit()
    await db.refresh(payment)
    return payment
