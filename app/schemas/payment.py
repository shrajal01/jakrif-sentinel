from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    """
    Schema for creating a new payment.
    """
    amount: Decimal = Field(..., gt=0, description="Payment amount must be greater than 0")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Currency code (e.g., USD)")
    merchant_reference: Optional[str] = Field(None, max_length=255, description="Merchant's internal reference")
    description: Optional[str] = Field(None, max_length=500, description="Payment description")


class PaymentResponse(BaseModel):
    """
    Schema for payment response.
    """
    id: int
    payment_id: UUID
    amount: Decimal
    currency: str
    status: PaymentStatus
    merchant_reference: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentListResponse(BaseModel):
    """
    Schema for a list of payments.
    """
    items: List[PaymentResponse]
    total: int
