"""Sales & Accounting dashboard API — a server-side proxy in front of ERPNext.

Run:  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .cache import cached, clear_cache
from .config import get_settings
from .dates import DateRange, date_range
from .erpnext_client import ERPNextError, close_client, get_client
from .routers import accounting as accounting_router
from .routers import sales as sales_router
from .services import accounting, sales

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_client()
    yield
    await close_client()


app = FastAPI(title="Sindh Bakery Sales & Accounting API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(ERPNextError)
async def erpnext_error_handler(_: Request, exc: ERPNextError):
    return JSONResponse(status_code=502, content={"detail": f"ERPNext error: {exc.message}", "upstream_status": exc.status_code})


app.include_router(sales_router.router)
app.include_router(accounting_router.router)


@app.get("/api/health")
async def health():
    try:
        user = await get_client().ping()
        return {"status": "ok", "erpnext_user": user, "company": settings.erpnext_company,
                "server_time": datetime.now(timezone.utc).isoformat()}
    except ERPNextError as exc:
        return JSONResponse(status_code=503, content={"status": "error", "detail": exc.message})


@app.get("/api/summary")
async def summary(rng: DateRange = Depends(date_range), refresh: bool = False):
    """Combined Sales + Accounting summary for the 'All' tab in one call."""
    async def build():
        k, p, r, c, o = await asyncio.gather(
            sales.kpis(rng), accounting.pnl(rng), accounting.receivables(rng), accounting.cash_position(rng),
            sales.by_outlet(rng),
        )
        return {"range": rng.as_dict(), "sales": k, "pnl": p, "receivables": r, "cash": c, "outlets": o}

    value, hit = await cached(f"summary:{rng.key()}", build, refresh=refresh)
    return {**value, "cached": hit}


@app.post("/api/cache/clear")
async def cache_clear():
    clear_cache()
    return {"status": "cleared"}
