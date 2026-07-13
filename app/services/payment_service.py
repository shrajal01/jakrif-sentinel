import asyncio
import uuid
import logging
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

logger = logging.getLogger(__name__)


async def create_payment(db: AsyncSession, payment_in: PaymentCreate, idempotency_key: Optional[str] = None) -> Payment:
    """
    Create a new payment record.
    Generates a UUID automatically and defaults status to CREATED.
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
                logger.info(f"Idempotency HIT for key: {idempotency_key}. Duplicate prevented.")
                return deserialize_payment(cached)
            
            logger.info(f"Idempotency MISS for key: {idempotency_key}. Proceeding to acquire lock.")
            
            # 2. Acquire a short-lived lock to prevent race conditions during concurrent identical requests
            lock_acquired = await redis_service.set_if_not_exists(lock_key, "locked", expire_seconds=30)
            
            if lock_acquired:
                logger.info(f"Lock acquired for {idempotency_key}.")
            else:
                # Lock exists: Another identical request is currently processing. Wait briefly to see if it finishes.
                logger.info(f"Idempotency lock exists for {idempotency_key}. Waiting briefly...")
                await asyncio.sleep(0.5)
                
                # 3. Check cache one last time after waiting
                cached = await redis_service.get(redis_key)
                if cached:
                    logger.info(f"Idempotency HIT after wait for key: {idempotency_key}. Duplicate prevented.")
                    return deserialize_payment(cached)
                else:
                    logger.warning(f"Idempotency lock conflict for {idempotency_key}. Returning 409.")
                    raise HTTPException(
                        status_code=http_status.HTTP_409_CONFLICT,
                        detail="A request with this Idempotency-Key is currently being processed."
                    )
        except HTTPException:
            # Re-raise HTTP exceptions so we don't accidentally swallow the 409 Conflict
            raise
        except Exception as e:
            # Gracefully handle Redis failures. We log the error but allow processing to continue normally.
            logger.warning(f"Redis unavailable or failed during idempotency check: {e}. Proceeding without idempotency.")
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

        try:
            await publish_payment_event({
                "payment_id": str(payment.payment_id),
                "amount": float(payment.amount),
                "currency": payment.currency,
                "merchant_reference": payment.merchant_reference,
            })
        except Exception as e:
            logger.error(f"Failed to publish payment event for payment {payment.id}: {e}")

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
                logger.info(f"Cached idempotency response for {idempotency_key}")
            except Exception as e:
                logger.warning(f"Failed to cache response in Redis: {e}")

        return payment

    finally:
        # 5. Ensure the lock is released so future retries aren't blocked if processing fails
        if lock_key and redis_available:
            try:
                await redis_service.delete(lock_key)
                logger.info(f"Lock released for {idempotency_key}.")
            except Exception as e:
                logger.warning(f"Failed to release Redis lock: {e}")


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
