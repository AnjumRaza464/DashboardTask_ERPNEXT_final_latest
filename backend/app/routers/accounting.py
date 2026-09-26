from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..cache import cached
from ..dates import DateRange, date_range
from ..services import accounting

router = APIRouter(prefix="/api/accounting", tags=["accounting"])


def _stamp(payload: dict[str, Any], was_cached: bool) -> dict[str, Any]:
    return {**payload, "cached": was_cached}


@router.get("/pnl")
async def pnl(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:pnl:{rng.key()}", lambda: accounting.pnl(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/pnl-trend")
async def pnl_trend(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:pnl-trend:{rng.key()}", lambda: accounting.pnl_trend(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/receivables")
async def receivables(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:ar:{rng.key()}", lambda: accounting.receivables(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/cash-position")
async def cash_position(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:cash:{rng.key()}", lambda: accounting.cash_position(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/payables")
async def payables(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:ap:{rng.key()}", lambda: accounting.payables(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/purchases-trend")
async def purchases_trend(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:purchases:{rng.key()}", lambda: accounting.purchases_trend(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/cash-flow")
async def cash_flow(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:cashflow:{rng.key()}", lambda: accounting.cash_flow(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/expense-trend")
async def expense_trend(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:exptrend:{rng.key()}", lambda: accounting.expense_trend(rng), refresh=refresh)
    return _stamp(value, hit)


@router.get("/balance-sheet")
async def balance_sheet(rng: DateRange = Depends(date_range), refresh: bool = False):
    value, hit = await cached(f"acc:bs:{rng.key()}", lambda: accounting.balance_sheet(rng), refresh=refresh)
    return _stamp(value, hit)
