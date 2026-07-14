from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database.session import get_db
from app.schemas.payment import PaymentCreate, PaymentResponse, PaymentListResponse
from app.services import payment_service
from app.core.context import correlation_id as correlation_id_var


router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment",
)
async def create_payment(
    payment_in: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Create a new payment.
    Note: The payment state machine is not implemented yet.
    """
    return await payment_service.create_payment(
        db=db,
        payment_in=payment_in,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id_var.get(),
    )


@router.get(
    "",
    response_model=PaymentListResponse,
    summary="Get all payments",
)
async def get_payments(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a list of payments.
    """
    items, total = await payment_service.list_payments(db=db, skip=skip, limit=limit)
    return {"items": items, "total": total}


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment by ID",
)
async def get_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a specific payment by its ID.
    """
    payment = await payment_service.get_payment(db=db, payment_id=payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    return payment
