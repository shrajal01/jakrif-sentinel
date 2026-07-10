import uuid
from typing import Optional, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentCreate


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


async def update_payment_status(db: AsyncSession, payment_id: int, status: PaymentStatus) -> Payment:
    """
    Update the status of an existing payment.
    Validates payment existence before updating.
    """
    payment = await get_payment(db, payment_id)
    if not payment:
        raise ValueError(f"Payment with id {payment_id} does not exist.")
        
    payment.status = status
    await db.commit()
    await db.refresh(payment)
    return payment
