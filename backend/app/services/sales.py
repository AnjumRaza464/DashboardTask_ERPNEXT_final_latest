"""Sales figures straight from Sales Invoice / Sales Invoice Item."""
from __future__ import annotations

import asyncio
from typing import Any

import pandas as pd

from ..dates import DateRange
from ..erpnext_client import get_client

INVOICE_FIELDS = [
    "name", "posting_date", "posting_time", "customer", "customer_name",
    "base_grand_total", "base_net_total", "total_taxes_and_charges", "discount_amount",
    "outstanding_amount", "status", "is_return", "is_pos", "cost_center",
    "pos_profile", "set_warehouse", "total_qty", "due_date",
]


def _base_filters(rng: DateRange) -> list[list[Any]]:
    c = get_client()
    return [
        ["docstatus", "=", 1],
        ["company", "=", c.company],
        ["posting_date", ">=", rng.start.isoformat()],
        ["posting_date", "<=", rng.end.isoformat()],
    ]


def outlet_label(cost_center: str | None, pos_profile: str | None = None, warehouse: str | None = None) -> str:
    raw = cost_center or pos_profile or warehouse or "Unassigned"
    abbr = f" - {get_client().company.split()[0][:1]}"  # not reliable; strip generic suffix below
    label = raw.strip()
    # Strip the trailing " - <ABBR>" company suffix ERPNext appends to account/cost-center names
    if " - " in label:
        head, _, tail = label.rpartition(" - ")
        if tail.isupper() and len(tail) <= 5:
            label = head
    _ = abbr
    return label.strip() or "Unassigned"


async def _period_totals(rng: DateRange) -> dict[str, float]:
    c = get_client()
    rows = await c.get_list(
        "Sales Invoice",
        ["count(name) as invoice_count", "sum(base_grand_total) as total_sales",
         "sum(outstanding_amount) as outstanding", "sum(total_qty) as total_qty"],
        _base_filters(rng) + [["is_return", "=", 0]],
        limit_page_length=1,
    )
    returns = await c.get_list(
        "Sales Invoice",
        ["count(name) as return_count", "sum(base_grand_total) as return_total"],
        _base_filters(rng) + [["is_return", "=", 1]],
        limit_page_length=1,
    )
    r = rows[0] if rows else {}
    ret = returns[0] if returns else {}
    gross = float(r.get("total_sales") or 0)
    ret_total = float(ret.get("return_total") or 0)  # negative in ERPNext
    count = int(r.get("invoice_count") or 0)
    net = gross + ret_total
    return {
        "total_sales": round(net, 2),
        "gross_sales": round(gross, 2),
        "returns_total": round(ret_total, 2),
        "invoice_count": count,
        "return_count": int(ret.get("return_count") or 0),
        "avg_invoice_value": round(gross / count, 2) if count else 0.0,
        "outstanding": round(float(r.get("outstanding") or 0), 2),
        "total_qty": round(float(r.get("total_qty") or 0), 3),
    }


async def kpis(rng: DateRange) -> dict[str, Any]:
    current, previous = await asyncio.gather(_period_totals(rng), _period_totals(rng.previous()))
    deltas = {}
    for k in ("total_sales", "invoice_count", "avg_invoice_value", "outstanding", "total_qty"):
        prev = previous[k]
        deltas[k] = round((current[k] - prev) / prev * 100, 1) if prev else None
    return {
        "source": "sales_invoice",
        "range": rng.as_dict(),
        "previous_range": rng.previous().as_dict(),
        "current": current,
        "previous": previous,
        "delta_pct": deltas,
    }


async def invoices(rng: DateRange) -> dict[str, Any]:
    rows = await get_client().get_all(
        "Sales Invoice", INVOICE_FIELDS, _base_filters(rng), order_by="posting_date desc, posting_time desc",
    )
    for r in rows:
        r["outlet"] = outlet_label(r.get("cost_center"), r.get("pos_profile"), r.get("set_warehouse"))
        if r.get("posting_time"):
            r["posting_time"] = str(r["posting_time"])[:8]
    return {"source": "sales_invoice", "range": rng.as_dict(), "count": len(rows), "invoices": rows}


async def trend(rng: DateRange) -> dict[str, Any]:
    rows = await get_client().get_list(
        "Sales Invoice",
        ["posting_date", "sum(base_grand_total) as total", "count(name) as invoice_count"],
        _base_filters(rng),
        group_by="posting_date",
        order_by="posting_date asc",
        limit_page_length=None,
    )
    df = pd.DataFrame(rows, columns=["posting_date", "total", "invoice_count"])
    granularity = rng.granularity
    if df.empty:
        points: list[dict[str, Any]] = []
    else:
        df["posting_date"] = pd.to_datetime(df["posting_date"])
        # Fill missing days with zero so the line does not skip gaps
        full = pd.date_range(rng.start, rng.end, freq="D")
        df = df.set_index("posting_date").reindex(full, fill_value=0).rename_axis("period").reset_index()
        if granularity == "month":
            df = df.groupby(df["period"].dt.to_period("M")).agg({"total": "sum", "invoice_count": "sum"}).reset_index()
            df["period"] = df["period"].dt.to_timestamp()
        points = [
            {"period": p.strftime("%Y-%m-%d"), "total": round(float(t), 2), "invoice_count": int(n)}
            for p, t, n in zip(df["period"], df["total"], df["invoice_count"])
        ]
    return {"source": "sales_invoice", "range": rng.as_dict(), "granularity": granularity, "points": points}


async def top_items(rng: DateRange, limit: int = 10) -> dict[str, Any]:
    c = get_client()
    names = [r["name"] for r in await c.get_all("Sales Invoice", ["name"], _base_filters(rng))]
    if not names:
        return {"source": "sales_invoice_item", "range": rng.as_dict(), "items": [], "total_amount": 0.0}

    chunks = [names[i:i + 200] for i in range(0, len(names), 200)]
    results = await asyncio.gather(*[
        c.get_list(
            "Sales Invoice Item",
            ["item_code", "item_name", "item_group", "sum(qty) as qty", "sum(base_amount) as amount"],
            [["parent", "in", chunk]],
            group_by="item_code",
            parent="Sales Invoice",
            limit_page_length=None,
        )
        for chunk in chunks
    ])
    rows = [r for chunk in results for r in chunk]
    df = pd.DataFrame(rows, columns=["item_code", "item_name", "item_group", "qty", "amount"])
    if df.empty:
        return {"source": "sales_invoice_item", "range": rng.as_dict(), "items": [], "total_amount": 0.0}
    df = df.groupby(["item_code"], as_index=False).agg(
        item_name=("item_name", "first"), item_group=("item_group", "first"), qty=("qty", "sum"), amount=("amount", "sum")
    ).sort_values("amount", ascending=False)
    total = float(df["amount"].sum())
    top = df.head(limit)
    items = [
        {
            "item_code": r.item_code, "item_name": r.item_name or r.item_code, "item_group": r.item_group,
            "qty": round(float(r.qty), 3), "amount": round(float(r.amount), 2),
            "share_pct": round(float(r.amount) / total * 100, 1) if total else 0.0,
        }
        for r in top.itertuples()
    ]
    other = float(df.iloc[limit:]["amount"].sum()) if len(df) > limit else 0.0
    return {
        "source": "sales_invoice_item", "range": rng.as_dict(), "items": items,
        "other_amount": round(other, 2), "total_amount": round(total, 2), "distinct_items": int(len(df)),
    }


async def by_outlet(rng: DateRange) -> dict[str, Any]:
    rows = await get_client().get_list(
        "Sales Invoice",
        ["cost_center", "pos_profile", "set_warehouse", "sum(base_grand_total) as total",
         "count(name) as invoice_count", "sum(outstanding_amount) as outstanding"],
        _base_filters(rng),
        group_by="cost_center, pos_profile",
        order_by="total desc",
        limit_page_length=None,
    )
    outlets = []
    grand = sum(float(r.get("total") or 0) for r in rows)
    for r in rows:
        total = float(r.get("total") or 0)
        count = int(r.get("invoice_count") or 0)
        outlets.append({
            "outlet": outlet_label(r.get("cost_center"), r.get("pos_profile"), r.get("set_warehouse")),
            "cost_center": r.get("cost_center"), "pos_profile": r.get("pos_profile"),
            "total": round(total, 2), "invoice_count": count,
            "avg_invoice_value": round(total / count, 2) if count else 0.0,
            "outstanding": round(float(r.get("outstanding") or 0), 2),
            "share_pct": round(total / grand * 100, 1) if grand else 0.0,
        })
    return {"source": "sales_invoice", "range": rng.as_dict(), "outlets": outlets, "total": round(grand, 2)}


# ------------------------------------------------------------ analytics
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
VALUE_BUCKETS = [
    (0, 1_000, "< 1K"), (1_000, 5_000, "1K-5K"), (5_000, 10_000, "5K-10K"), (10_000, 25_000, "10K-25K"),
    (25_000, 50_000, "25K-50K"), (50_000, 100_000, "50K-100K"), (100_000, 500_000, "100K-500K"),
    (500_000, 1_000_000, "500K-1M"), (1_000_000, float("inf"), "> 1M"),
]


async def _invoice_frame(rng: DateRange) -> pd.DataFrame:
    """Invoice-level rows for the range, shared by the pattern endpoints (cached)."""
    from ..cache import cached  # local import: cache imports config, not services, but keep it lazy

    async def _load() -> list[dict[str, Any]]:
        return await get_client().get_all(
            "Sales Invoice",
            ["name", "posting_date", "posting_time", "customer", "customer_name", "base_grand_total", "total_qty", "is_return"],
            _base_filters(rng),
        )

    rows, _ = await cached(f"sales:frame:{rng.key()}", _load)
    cols = ["name", "posting_date", "posting_time", "customer", "customer_name", "base_grand_total", "total_qty", "is_return"]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        return df
    df["base_grand_total"] = df["base_grand_total"].astype(float)
    df["total_qty"] = df["total_qty"].astype(float)
    df["is_return"] = df["is_return"].fillna(0).astype(int)
    df["posting_date"] = pd.to_datetime(df["posting_date"])
    df["hour"] = pd.to_numeric(df["posting_time"].astype(str).str.slice(0, 2), errors="coerce")
    return df


async def compare(rng: DateRange) -> dict[str, Any]:
    """Current period vs the previous same-length period, aligned by position."""
    prev = rng.previous()
    cur_t, prev_t = await asyncio.gather(trend(rng), trend(prev))
    cur_pts, prev_pts = cur_t["points"], prev_t["points"]
    n = max(len(cur_pts), len(prev_pts))
    points = []
    for i in range(n):
        c = cur_pts[i] if i < len(cur_pts) else None
        p = prev_pts[i] if i < len(prev_pts) else None
        points.append({
            "index": i + 1,
            "period": c["period"] if c else None,
            "previous_period": p["period"] if p else None,
            "current": c["total"] if c else None,
            "previous": p["total"] if p else None,
        })
    cur_total = sum(p["total"] for p in cur_pts)
    prev_total = sum(p["total"] for p in prev_pts)
    return {
        "source": "sales_invoice", "range": rng.as_dict(), "previous_range": prev.as_dict(),
        "granularity": cur_t["granularity"], "points": points,
        "current_total": round(cur_total, 2), "previous_total": round(prev_total, 2),
        "delta_pct": round((cur_total - prev_total) / prev_total * 100, 1) if prev_total else None,
    }


async def by_item_group(rng: DateRange) -> dict[str, Any]:
    c = get_client()
    names = [r["name"] for r in await c.get_all("Sales Invoice", ["name"], _base_filters(rng))]
    empty = {"source": "sales_invoice_item", "range": rng.as_dict(), "groups": [], "total_amount": 0.0}
    if not names:
        return empty
    chunks = [names[i:i + 200] for i in range(0, len(names), 200)]
    results = await asyncio.gather(*[
        c.get_list(
            "Sales Invoice Item",
            ["item_group", "sum(qty) as qty", "sum(base_amount) as amount", "count(distinct item_code) as items"],
            [["parent", "in", chunk]], group_by="item_group", parent="Sales Invoice", limit_page_length=None,
        )
        for chunk in chunks
    ])
    df = pd.DataFrame([r for ch in results for r in ch], columns=["item_group", "qty", "amount", "items"])
    if df.empty:
        return empty
    df["item_group"] = df["item_group"].fillna("Ungrouped")
    df = df.groupby("item_group", as_index=False).agg(qty=("qty", "sum"), amount=("amount", "sum"), items=("items", "max"))
    df = df.sort_values("amount", ascending=False)
    total = float(df["amount"].sum())
    groups = [
        {"item_group": r.item_group, "qty": round(float(r.qty), 3), "amount": round(float(r.amount), 2),
         "items": int(r.items), "share_pct": round(float(r.amount) / total * 100, 1) if total else 0.0}
        for r in df.itertuples()
    ]
    return {**empty, "groups": groups, "total_amount": round(total, 2)}


async def by_hour(rng: DateRange) -> dict[str, Any]:
    df = await _invoice_frame(rng)
    sales_df = df[df["is_return"] == 0] if not df.empty else df
    active_days = int(sales_df["posting_date"].nunique()) if not sales_df.empty else 0
    points = []
    for h in range(24):
        sub = sales_df[sales_df["hour"] == h] if not sales_df.empty else sales_df
        total = float(sub["base_grand_total"].sum()) if not sub.empty else 0.0
        points.append({
            "hour": h, "label": f"{h:02d}:00", "total": round(total, 2), "invoice_count": int(len(sub)),
            "avg_per_day": round(total / active_days, 2) if active_days else 0.0,
        })
    peak = max(points, key=lambda p: p["total"]) if any(p["total"] for p in points) else None
    return {"source": "sales_invoice", "range": rng.as_dict(), "active_days": active_days,
            "points": points, "peak_hour": peak["hour"] if peak else None}


async def by_weekday(rng: DateRange) -> dict[str, Any]:
    df = await _invoice_frame(rng)
    sales_df = df[df["is_return"] == 0] if not df.empty else df
    days = pd.date_range(rng.start, rng.end, freq="D")
    occurrences = pd.Series(days.dayofweek).value_counts().to_dict()
    points = []
    for i, name in enumerate(WEEKDAYS):
        sub = sales_df[sales_df["posting_date"].dt.dayofweek == i] if not sales_df.empty else sales_df
        total = float(sub["base_grand_total"].sum()) if not sub.empty else 0.0
        occ = int(occurrences.get(i, 0))
        points.append({
            "weekday": name, "total": round(total, 2), "invoice_count": int(len(sub)), "occurrences": occ,
            "avg_per_day": round(total / occ, 2) if occ else 0.0,
        })
    best = max(points, key=lambda p: p["avg_per_day"]) if any(p["total"] for p in points) else None
    return {"source": "sales_invoice", "range": rng.as_dict(), "points": points,
            "best_weekday": best["weekday"] if best else None}


async def invoice_distribution(rng: DateRange) -> dict[str, Any]:
    df = await _invoice_frame(rng)
    sales_df = df[df["is_return"] == 0] if not df.empty else df
    vals = sales_df["base_grand_total"] if not sales_df.empty else pd.Series(dtype=float)
    buckets = []
    for lo, hi, label in VALUE_BUCKETS:
        sub = vals[(vals >= lo) & (vals < hi)]
        buckets.append({"bucket": label, "min": lo, "max": None if hi == float("inf") else hi,
                        "invoice_count": int(len(sub)), "total": round(float(sub.sum()), 2)})
    n = int(len(vals))
    stats = {
        "count": n,
        "median": round(float(vals.median()), 2) if n else 0.0,
        "mean": round(float(vals.mean()), 2) if n else 0.0,
        "min": round(float(vals.min()), 2) if n else 0.0,
        "max": round(float(vals.max()), 2) if n else 0.0,
        "p90": round(float(vals.quantile(0.9)), 2) if n else 0.0,
    }
    return {"source": "sales_invoice", "range": rng.as_dict(), "buckets": buckets, "stats": stats}


async def top_customers(rng: DateRange, limit: int = 10) -> dict[str, Any]:
    rows = await get_client().get_list(
        "Sales Invoice",
        ["customer", "customer_name", "sum(base_grand_total) as total", "count(name) as invoice_count",
         "sum(outstanding_amount) as outstanding", "max(posting_date) as last_invoice"],
        _base_filters(rng), group_by="customer", order_by="total desc", limit_page_length=None,
    )
    grand = sum(float(r.get("total") or 0) for r in rows)
    customers = []
    for r in rows[:limit]:
        total = float(r.get("total") or 0)
        count = int(r.get("invoice_count") or 0)
        customers.append({
            "customer": r["customer"], "customer_name": r.get("customer_name") or r["customer"],
            "total": round(total, 2), "invoice_count": count,
            "avg_invoice_value": round(total / count, 2) if count else 0.0,
            "outstanding": round(float(r.get("outstanding") or 0), 2), "last_invoice": str(r.get("last_invoice") or ""),
            "share_pct": round(total / grand * 100, 1) if grand else 0.0,
        })
    return {"source": "sales_invoice", "range": rng.as_dict(), "customers": customers,
            "distinct_customers": len(rows), "total": round(grand, 2)}


async def payment_modes(rng: DateRange) -> dict[str, Any]:
    c = get_client()
    inv = await c.get_list(
        "Sales Invoice",
        ["name", "base_grand_total", "base_change_amount", "base_rounding_adjustment", "outstanding_amount", "is_pos"],
        _base_filters(rng) + [["is_return", "=", 0]], limit_page_length=None,
    )
    names = [r["name"] for r in inv]
    if not names:
        return {"source": "sales_invoice", "range": rng.as_dict(), "modes": [], "total": 0.0}
    chunks = [names[i:i + 200] for i in range(0, len(names), 200)]
    results = await asyncio.gather(*[
        c.get_list("Sales Invoice Payment", ["mode_of_payment", "sum(base_amount) as amount", "count(name) as n"],
                   [["parent", "in", chunk]], group_by="mode_of_payment", parent="Sales Invoice", limit_page_length=None)
        for chunk in chunks
    ])
    paid: dict[str, dict[str, float]] = {}
    for ch in results:
        for r in ch:
            m = r.get("mode_of_payment") or "Unspecified"
            d = paid.setdefault(m, {"amount": 0.0, "n": 0})
            d["amount"] += float(r.get("amount") or 0)
            d["n"] += int(r.get("n") or 0)
    change = sum(float(r.get("base_change_amount") or 0) for r in inv)
    grand = sum(float(r.get("base_grand_total") or 0) for r in inv)
    # POS change is handed back to the customer: net it off the largest mode (cash)
    if change and paid:
        biggest = max(paid, key=lambda k: paid[k]["amount"])
        paid[biggest]["amount"] -= change
    collected = sum(d["amount"] for d in paid.values())
    # payments settle the *rounded* total, so add the rounding back before looking for unpaid credit
    rounding = sum(float(r.get("base_rounding_adjustment") or 0) for r in inv)
    credit = max(0.0, grand + rounding - collected)
    if credit < 1.0:
        credit = 0.0
    modes = [{"mode": m, "amount": round(d["amount"], 2), "count": int(d["n"])} for m, d in paid.items()]
    if credit > 0.5:
        credit_count = sum(1 for r in inv if not r.get("is_pos") or float(r.get("outstanding_amount") or 0) > 0)
        modes.append({"mode": "Credit / Unpaid", "amount": round(credit, 2), "count": credit_count})
    modes.sort(key=lambda m: m["amount"], reverse=True)
    for m in modes:
        m["share_pct"] = round(m["amount"] / grand * 100, 1) if grand else 0.0
    return {"source": "sales_invoice", "range": rng.as_dict(), "modes": modes, "total": round(grand, 2)}


async def composition(rng: DateRange) -> dict[str, Any]:
    """Gross -> discounts -> taxes -> returns -> net sales (waterfall)."""
    c = get_client()
    rows = await c.get_list(
        "Sales Invoice",
        ["sum(base_total) as gross", "sum(base_discount_amount) as discount", "sum(base_net_total) as net",
         "sum(base_total_taxes_and_charges) as taxes", "sum(base_grand_total) as grand", "count(name) as n"],
        _base_filters(rng) + [["is_return", "=", 0]], limit_page_length=1,
    )
    ret = await c.get_list(
        "Sales Invoice", ["sum(base_grand_total) as total", "count(name) as n"],
        _base_filters(rng) + [["is_return", "=", 1]], limit_page_length=1,
    )
    r = rows[0] if rows else {}
    rr = ret[0] if ret else {}
    gross = float(r.get("gross") or 0)
    discount = float(r.get("discount") or 0)
    taxes = float(r.get("taxes") or 0)
    grand = float(r.get("grand") or 0)
    returns = float(rr.get("total") or 0)  # already negative in ERPNext
    net_sales = grand + returns
    rounding = grand - (gross - discount + taxes)
    steps = [
        {"label": "Gross", "amount": round(gross, 2), "kind": "total"},
        {"label": "Discounts", "amount": round(-discount, 2), "kind": "delta"},
        {"label": "Taxes", "amount": round(taxes, 2), "kind": "delta"},
    ]
    if abs(rounding) >= 0.5:
        steps.append({"label": "Rounding", "amount": round(rounding, 2), "kind": "delta"})
    steps.append({"label": "Returns", "amount": round(returns, 2), "kind": "delta"})
    steps.append({"label": "Net Sales", "amount": round(net_sales, 2), "kind": "total"})
    return {
        "source": "sales_invoice", "range": rng.as_dict(), "steps": steps,
        "gross": round(gross, 2), "discount": round(discount, 2), "taxes": round(taxes, 2),
        "returns": round(returns, 2), "net_sales": round(net_sales, 2),
        "invoice_count": int(r.get("n") or 0), "return_count": int(rr.get("n") or 0),
        "discount_pct": round(discount / gross * 100, 2) if gross else 0.0,
    }
