import uuid
import logging
from typing import Optional, List, Tuple

from fastapi import HTTPException, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentCreate
from worker.publisher import publish_payment_event

logger = logging.getLogger(__name__)


async def create_payment(db: AsyncSession, payment_in: PaymentCreate) -> Payment:
    """
    Create a new payment record.
    Generates a UUID automatically and defaults status to CREATED.
    """
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
            "id": payment.id,
            "payment_id": str(payment.payment_id),
            "amount": float(payment.amount),
            "currency": payment.currency,
            "status": payment.status.value,
            "merchant_reference": payment.merchant_reference,
            "description": payment.description,
        })
    except Exception as e:
        logger.error(f"Failed to publish payment event for payment {payment.id}: {e}")
        # The payment was already saved to the database successfully.
        # Failing here would return an error to the user even though their payment
        # record exists. We log the failure so it can be monitored, but the
        # creation process should still succeed to avoid data inconsistency.

    return payment


async def get_payment(db: AsyncSession, payment_id: int) -> Optional[Payment]:
    """
    Retrieve a payment by its internal ID.
    """
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
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
