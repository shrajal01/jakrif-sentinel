"""
Small helper for resolving the internal `Service` row that `RequestLog` and
`RetryAttempt` rows must reference (both have a NOT NULL `service_id` FK).

The API and worker are each treated as one logical "service" for observability
purposes. The row is created lazily on first use and its id is cached
in-process afterwards to avoid a lookup on every request/message.
"""
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.service import Service

# Process-local cache: service name -> id
_service_id_cache: Dict[str, int] = {}


async def get_or_create_service_id(db: AsyncSession, name: str, base_url: str = "internal") -> int:
    """
    Return the id of the Service row identified by `name`, creating it if it
    doesn't exist yet. Safe to call concurrently: if two callers race to
    create the same row, the unique constraint on `name` is handled by
    re-querying instead of raising.
    """
    cached = _service_id_cache.get(name)
    if cached is not None:
        return cached

    result = await db.execute(select(Service).where(Service.name == name))
    service = result.scalar_one_or_none()

    if service is None:
        service = Service(name=name, base_url=base_url, description=f"Auto-registered service: {name}")
        db.add(service)
        try:
            await db.commit()
            await db.refresh(service)
        except IntegrityError:
            await db.rollback()
            result = await db.execute(select(Service).where(Service.name == name))
            service = result.scalar_one()

    _service_id_cache[name] = service.id
    return service.id