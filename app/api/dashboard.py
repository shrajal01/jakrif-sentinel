from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Dict, Any
import aio_pika

from app.database.session import get_db
from app.models.payment import Payment, PaymentStatus
from app.models.request_log import RequestLog
from app.core.config import settings
from worker.config import settings as worker_settings
from app.core.logging import get_logger

logger = get_logger("api.dashboard")

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

async def get_queue_size(queue_name: str) -> int:
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(queue_name, durable=True)
            return queue.declaration_result.message_count
    except Exception as e:
        logger.error(f"Error fetching queue size for {queue_name}", error=str(e))
        return 0

@router.get("/stats", summary="Get payment processing stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Total payments
    total_result = await db.execute(select(func.count(Payment.id)))
    total_payments = total_result.scalar() or 0

    # Successful payments
    success_result = await db.execute(select(func.count(Payment.id)).where(Payment.status == PaymentStatus.SUCCESS))
    successful_payments = success_result.scalar() or 0

    # Failed payments
    failed_result = await db.execute(select(func.count(Payment.id)).where(Payment.status == PaymentStatus.FAILED))
    failed_payments = failed_result.scalar() or 0

    # Processing payments (CREATED, ENQUEUED, PROCESSING)
    processing_result = await db.execute(
        select(func.count(Payment.id)).where(
            Payment.status.in_([PaymentStatus.CREATED, PaymentStatus.ENQUEUED, PaymentStatus.PROCESSING])
        )
    )
    processing_payments = processing_result.scalar() or 0

    # RabbitMQ Queue sizes
    retry_count = await get_queue_size(worker_settings.PAYMENTS_RETRY_QUEUE_NAME)
    dlq_count = await get_queue_size(worker_settings.PAYMENTS_DEAD_LETTER_QUEUE_NAME)

    return {
        "total_payments": total_payments,
        "successful_payments": successful_payments,
        "failed_payments": failed_payments,
        "processing_payments": processing_payments,
        "retry_queue_count": retry_count,
        "dead_letter_queue_count": dlq_count
    }

@router.get("/recent-payments", summary="Get recent payments")
async def get_recent_payments(limit: int = 10, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Payment).order_by(desc(Payment.created_at)).limit(limit)
    )
    payments = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "payment_id": str(p.payment_id),
            "amount": float(p.amount),
            "currency": p.currency,
            "status": p.status.value,
            "merchant_reference": p.merchant_reference,
            "created_at": p.created_at,
            "updated_at": p.updated_at
        }
        for p in payments
    ]

@router.get("/recent-logs", summary="Get recent request logs")
async def get_recent_logs(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RequestLog).order_by(desc(RequestLog.created_at)).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "request_id": l.request_id,
            "service_id": l.service_id,
            "method": l.method,
            "path": l.path,
            "status_code": l.status_code,
            "latency_ms": l.latency_ms,
            "response_size": l.response_size,
            "created_at": l.created_at
        }
        for l in logs
    ]
