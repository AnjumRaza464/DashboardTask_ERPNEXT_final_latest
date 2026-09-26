from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ..cache import cached
from ..dates import DateRange, date_range
from ..services import sales

router = APIRouter(prefix="/api/sales", tags=["sales"])


def _stamp(payload: dict[str, Any], was_cached: bool) -> dict[str, Any]:
    return {**payload, "cached": was_cached}


@router.get("/kpis")
async def sales_kpis(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:kpis:{rng.key()}", lambda: sales.kpis(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/invoices")
async def sales_invoices(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:invoices:{rng.key()}", lambda: sales.invoices(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/trend")
async def sales_trend(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:trend:{rng.key()}", lambda: sales.trend(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/top-items")
async def sales_top_items(
    rng: DateRange = Depends(date_range), limit: int = Query(default=10, ge=1, le=50), refresh: bool = False
):
    value, hit = await cached(f"sales:top:{rng.key()}:{limit}", lambda: sales.top_items(rng, limit), refresh=refresh)
    return _stamp(value, hit)


@router.get("/by-outlet")
async def sales_by_outlet(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:outlet:{rng.key()}", lambda: sales.by_outlet(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/compare")
async def sales_compare(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:compare:{rng.key()}", lambda: sales.compare(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/by-item-group")
async def sales_by_item_group(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:itemgroup:{rng.key()}", lambda: sales.by_item_group(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/by-hour")
async def sales_by_hour(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:hour:{rng.key()}", lambda: sales.by_hour(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/by-weekday")
async def sales_by_weekday(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:weekday:{rng.key()}", lambda: sales.by_weekday(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/invoice-distribution")
async def sales_invoice_distribution(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:dist:{rng.key()}", lambda: sales.invoice_distribution(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/top-customers")
async def sales_top_customers(
    rng: DateRange = Depends(date_range), limit: int = Query(default=10, ge=1, le=50), refresh: bool = False
):
    value, hit = await cached(f"sales:customers:{rng.key()}:{limit}", lambda: sales.top_customers(rng, limit), refresh=refresh)
    return _stamp(value, hit)


@router.get("/payment-modes")
async def sales_payment_modes(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:paymodes:{rng.key()}", lambda: sales.payment_modes(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/composition")
async def sales_composition(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"sales:composition:{rng.key()}", lambda: sales.composition(rng), refresh=refresh)
    return _stamp(value, hit)
