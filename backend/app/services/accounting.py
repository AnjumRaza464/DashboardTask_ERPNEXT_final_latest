"""Accounting figures.

Strategy: ask ERPNext's own report engine first (Profit and Loss Statement,
Accounts Receivable Summary, get_balance_on). Only if that call fails do we fall
back to aggregating raw GL Entry / Sales Invoice rows with pandas. Every payload
carries a `source` field: "erpnext_report" | "erpnext_api" | "raw_fallback" | "gl_entry".
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import pandas as pd

from ..cache import cached
from ..dates import DateRange
from ..erpnext_client import ERPNextError, get_client

log = logging.getLogger("dashboard.accounting")

AGEING_RANGES = ["0-30", "31-60", "61-90", "91-120", "121+"]


def _clean(name: str | None) -> str:
    if not name:
        return ""
    label = name.strip().strip("'")
    if " - " in label:
        head, _, tail = label.rpartition(" - ")
        if tail.isupper() and len(tail) <= 5:
            label = head
    return label.strip()


# --------------------------------------------------------------- accounts
async def account_map() -> dict[str, dict[str, Any]]:
    """name -> {root_type, account_type, is_group, parent_account}; cached with the rest."""
    async def _load() -> dict[str, dict[str, Any]]:
        rows = await get_client().get_all(
            "Account", ["name", "root_type", "account_type", "is_group", "parent_account", "account_name"],
            [["company", "=", get_client().company]],
        )
        return {r["name"]: r for r in rows}

    value, _ = await cached("accounts", _load)
    return value


def _cash_bank_accounts(accounts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    # NB: this instance has expense accounts wrongly typed as "Cash", hence the root_type guard.
    return [
        a for a in accounts.values()
        if a.get("root_type") == "Asset" and a.get("account_type") in ("Bank", "Cash") and not a.get("is_group")
    ]


# --------------------------------------------------------------------- P&L
def _parse_pnl_report(report: dict[str, Any], accounts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summary = {s.get("label"): float(s.get("value") or 0) for s in report.get("report_summary") or [] if s.get("label")}
    income_rows: list[dict[str, Any]] = []
    expense_rows: list[dict[str, Any]] = []
    for row in report.get("result") or []:
        acc = row.get("account")
        if not acc or row.get("is_group") or acc not in accounts:
            continue
        total = float(row.get("total") or 0)
        if total == 0:
            continue
        item = {"account": acc, "label": _clean(row.get("account_name") or acc), "amount": round(total, 2),
                "parent": _clean(row.get("parent_account"))}
        root = accounts[acc].get("root_type")
        if root == "Income":
            income_rows.append(item)
        elif root == "Expense":
            expense_rows.append(item)
    revenue = summary.get("Total Income")
    expenses = summary.get("Total Expense")
    net = summary.get("Net Profit", summary.get("Net Loss"))
    if revenue is None:
        revenue = sum(r["amount"] for r in income_rows)
    if expenses is None:
        expenses = sum(r["amount"] for r in expense_rows)
    if net is None:
        net = revenue - expenses
    return _pnl_payload(revenue, expenses, net, income_rows, expense_rows)


def _pnl_payload(revenue: float, expenses: float, net: float, income_rows: list, expense_rows: list) -> dict[str, Any]:
    expense_rows.sort(key=lambda r: abs(r["amount"]), reverse=True)
    income_rows.sort(key=lambda r: abs(r["amount"]), reverse=True)
    return {
        "revenue": round(revenue, 2),
        "expenses": round(expenses, 2),
        "net_profit": round(net, 2),
        "margin_pct": round(net / revenue * 100, 1) if revenue else None,
        "income_breakdown": income_rows,
        "expense_breakdown": expense_rows,
    }


async def _pnl_from_gl(rng: DateRange, accounts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    c = get_client()
    rows = await c.get_list(
        "GL Entry",
        ["account", "sum(debit) as debit", "sum(credit) as credit"],
        [["is_cancelled", "=", 0], ["company", "=", c.company],
         ["posting_date", ">=", rng.start.isoformat()], ["posting_date", "<=", rng.end.isoformat()]],
        group_by="account",
        limit_page_length=None,
    )
    df = pd.DataFrame(rows, columns=["account", "debit", "credit"])
    if df.empty:
        return _pnl_payload(0.0, 0.0, 0.0, [], [])
    df["root_type"] = df["account"].map(lambda a: accounts.get(a, {}).get("root_type"))
    df["debit"] = df["debit"].astype(float)
    df["credit"] = df["credit"].astype(float)
    inc = df[df.root_type == "Income"].assign(amount=lambda d: d.credit - d.debit)
    exp = df[df.root_type == "Expense"].assign(amount=lambda d: d.debit - d.credit)
    to_rows = lambda d: [  # noqa: E731
        {"account": r.account, "label": _clean(r.account), "amount": round(float(r.amount), 2),
         "parent": _clean(accounts.get(r.account, {}).get("parent_account"))}
        for r in d.itertuples() if float(r.amount) != 0
    ]
    revenue, expenses = float(inc.amount.sum()), float(exp.amount.sum())
    return _pnl_payload(revenue, expenses, revenue - expenses, to_rows(inc), to_rows(exp))


async def pnl(rng: DateRange) -> dict[str, Any]:
    c = get_client()
    accounts = await account_map()
    base = {"range": rng.as_dict(), "currency": "PKR"}
    try:
        report = await c.run_report("Profit and Loss Statement", {
            "company": c.company,
            "filter_based_on": "Date Range",
            "period_start_date": rng.start.isoformat(),
            "period_end_date": rng.end.isoformat(),
            "periodicity": "Yearly",
            "accumulated_values": 0,
            "include_default_book_entries": 1,
        })
        return {**base, "source": "erpnext_report", "report": "Profit and Loss Statement", **_parse_pnl_report(report, accounts)}
    except ERPNextError as exc:
        log.warning("P&L report failed (%s); falling back to GL Entry aggregation", exc.message)
        data = await _pnl_from_gl(rng, accounts)
        return {**base, "source": "raw_fallback", "fallback_reason": exc.message, **data}


async def pnl_trend(rng: DateRange) -> dict[str, Any]:
    """Income vs expense per day (or month for long ranges), from GL Entry aggregates."""
    c = get_client()
    accounts = await account_map()
    pl_accounts = [n for n, a in accounts.items() if a.get("root_type") in ("Income", "Expense") and not a.get("is_group")]
    rows = await c.get_list(
        "GL Entry",
        ["posting_date", "account", "sum(debit) as debit", "sum(credit) as credit"],
        [["is_cancelled", "=", 0], ["company", "=", c.company], ["account", "in", pl_accounts],
         ["posting_date", ">=", rng.start.isoformat()], ["posting_date", "<=", rng.end.isoformat()]],
        group_by="posting_date, account",
        order_by="posting_date asc",
        limit_page_length=None,
    )
    df = pd.DataFrame(rows, columns=["posting_date", "account", "debit", "credit"])
    granularity = rng.granularity
    if df.empty:
        return {"source": "gl_entry", "range": rng.as_dict(), "granularity": granularity, "points": []}
    df["posting_date"] = pd.to_datetime(df["posting_date"])
    df["root_type"] = df["account"].map(lambda a: accounts[a]["root_type"])
    df["debit"] = df["debit"].astype(float)
    df["credit"] = df["credit"].astype(float)
    df["income"] = ((df.credit - df.debit) * (df.root_type == "Income")).astype(float)
    df["expense"] = ((df.debit - df.credit) * (df.root_type == "Expense")).astype(float)
    daily = df.groupby("posting_date")[["income", "expense"]].sum()
    daily = daily.reindex(pd.date_range(rng.start, rng.end, freq="D"), fill_value=0.0).rename_axis("period")
    if granularity == "month":
        daily = daily.groupby(daily.index.to_period("M")).sum()
        daily.index = daily.index.to_timestamp()
    points = [
        {"period": p.strftime("%Y-%m-%d"), "income": round(float(i), 2), "expense": round(float(e), 2),
         "net": round(float(i - e), 2)}
        for p, i, e in zip(daily.index, daily["income"], daily["expense"])
    ]
    return {"source": "gl_entry", "range": rng.as_dict(), "granularity": granularity, "points": points}


# --------------------------------------------------------------- receivables
def _ar_payload(parties: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {k: 0.0 for k in AGEING_RANGES}
    total = 0.0
    for p in parties:
        total += p["outstanding"]
        for k in AGEING_RANGES:
            buckets[k] += p["ageing"].get(k, 0.0)
    parties.sort(key=lambda p: p["outstanding"], reverse=True)
    return {
        "total_outstanding": round(total, 2),
        "customer_count": len(parties),
        "ageing": [{"bucket": k, "amount": round(v, 2)} for k, v in buckets.items()],
        "top_customers": parties[:10],
    }


def _parse_ar_report(report: dict[str, Any]) -> dict[str, Any]:
    parties = []
    for row in report.get("result") or []:
        if not isinstance(row, dict) or not row.get("party"):
            continue
        outstanding = float(row.get("outstanding") or 0)
        ageing = {k: float(row.get(f"range{i + 1}") or 0) for i, k in enumerate(AGEING_RANGES)}
        parties.append({
            "customer": row.get("party"), "customer_name": row.get("party_name") or row.get("party"),
            "invoiced": round(float(row.get("invoiced") or 0), 2), "paid": round(float(row.get("paid") or 0), 2),
            "outstanding": round(outstanding, 2), "ageing": {k: round(v, 2) for k, v in ageing.items()},
        })
    return _ar_payload(parties)


async def _ar_from_invoices(as_on: date) -> dict[str, Any]:
    c = get_client()
    rows = await c.get_all(
        "Sales Invoice",
        ["customer", "customer_name", "posting_date", "due_date", "base_grand_total", "outstanding_amount"],
        [["docstatus", "=", 1], ["company", "=", c.company], ["outstanding_amount", "!=", 0],
         ["posting_date", "<=", as_on.isoformat()]],
    )
    df = pd.DataFrame(rows, columns=["customer", "customer_name", "posting_date", "due_date", "base_grand_total", "outstanding_amount"])
    if df.empty:
        return _ar_payload([])
    df["age"] = (pd.Timestamp(as_on) - pd.to_datetime(df["posting_date"])).dt.days.clip(lower=0)
    df["bucket"] = pd.cut(df["age"], bins=[-1, 30, 60, 90, 120, 10**6], labels=AGEING_RANGES)
    df["outstanding_amount"] = df["outstanding_amount"].astype(float)
    parties = []
    for (cust, name), g in df.groupby(["customer", "customer_name"]):
        ageing = g.groupby("bucket", observed=False)["outstanding_amount"].sum()
        parties.append({
            "customer": cust, "customer_name": name or cust,
            "invoiced": round(float(g["base_grand_total"].astype(float).sum()), 2), "paid": None,
            "outstanding": round(float(g["outstanding_amount"].sum()), 2),
            "ageing": {k: round(float(ageing.get(k, 0.0)), 2) for k in AGEING_RANGES},
        })
    return _ar_payload(parties)


async def receivables(rng: DateRange) -> dict[str, Any]:
    """Receivables are a point-in-time figure: evaluated as on the range end date."""
    c = get_client()
    base = {"range": rng.as_dict(), "as_on": rng.end.isoformat(), "currency": "PKR"}
    try:
        report = await c.run_report("Accounts Receivable Summary", {
            "company": c.company, "report_date": rng.end.isoformat(),
            "ageing_based_on": "Posting Date", "range": "30, 60, 90, 120",
        })
        return {**base, "source": "erpnext_report", "report": "Accounts Receivable Summary", **_parse_ar_report(report)}
    except ERPNextError as exc:
        log.warning("AR Summary report failed (%s); falling back to Sales Invoice ageing", exc.message)
        data = await _ar_from_invoices(rng.end)
        return {**base, "source": "raw_fallback", "fallback_reason": exc.message, **data}


# ------------------------------------------------------------- cash & bank
async def cash_position(rng: DateRange) -> dict[str, Any]:
    c = get_client()
    accounts = await account_map()
    targets = _cash_bank_accounts(accounts)
    base = {"range": rng.as_dict(), "as_on": rng.end.isoformat(), "currency": "PKR"}
    names = [a["name"] for a in targets]

    # Period movement (always from GL aggregates; cheap and exact)
    movement_rows = await c.get_list(
        "GL Entry", ["account", "sum(debit) as inflow", "sum(credit) as outflow"],
        [["is_cancelled", "=", 0], ["company", "=", c.company], ["account", "in", names],
         ["posting_date", ">=", rng.start.isoformat()], ["posting_date", "<=", rng.end.isoformat()]],
        group_by="account", limit_page_length=None,
    ) if names else []
    movement = {r["account"]: (float(r.get("inflow") or 0), float(r.get("outflow") or 0)) for r in movement_rows}

    source = "erpnext_api"
    reason = None
    balances: dict[str, float] = {}
    try:
        results = await asyncio.gather(*[
            c.call_method("erpnext.accounts.utils.get_balance_on", account=n, date=rng.end.isoformat(), company=c.company)
            for n in names
        ])
        balances = {n: float(v or 0) for n, v in zip(names, results)}
    except ERPNextError as exc:
        log.warning("get_balance_on failed (%s); falling back to GL Entry sums", exc.message)
        source, reason = "raw_fallback", exc.message
        rows = await c.get_list(
            "GL Entry", ["account", "sum(debit) as debit", "sum(credit) as credit"],
            [["is_cancelled", "=", 0], ["company", "=", c.company], ["account", "in", names],
             ["posting_date", "<=", rng.end.isoformat()]],
            group_by="account", limit_page_length=None,
        ) if names else []
        balances = {r["account"]: float(r.get("debit") or 0) - float(r.get("credit") or 0) for r in rows}

    items = []
    for a in targets:
        n = a["name"]
        inflow, outflow = movement.get(n, (0.0, 0.0))
        items.append({
            "account": n, "label": _clean(n), "type": a.get("account_type"),
            "balance": round(balances.get(n, 0.0), 2),
            "inflow": round(inflow, 2), "outflow": round(outflow, 2), "net_movement": round(inflow - outflow, 2),
        })
    items.sort(key=lambda i: i["balance"], reverse=True)
    total = sum(i["balance"] for i in items)
    return {
        **base, "source": source, **({"fallback_reason": reason} if reason else {}),
        "total": round(total, 2),
        "cash_total": round(sum(i["balance"] for i in items if i["type"] == "Cash"), 2),
        "bank_total": round(sum(i["balance"] for i in items if i["type"] == "Bank"), 2),
        "net_movement": round(sum(i["net_movement"] for i in items), 2),
        "accounts": items,
    }


# ------------------------------------------------------------------ payables
def _ap_payload(parties: list[dict[str, Any]]) -> dict[str, Any]:
    data = _ar_payload(parties)
    data["supplier_count"] = data.pop("customer_count")
    data["top_suppliers"] = data.pop("top_customers")
    return data


def _parse_ap_report(report: dict[str, Any]) -> dict[str, Any]:
    parties = []
    for row in report.get("result") or []:
        if not isinstance(row, dict) or not row.get("party"):
            continue
        outstanding = float(row.get("outstanding") or 0)
        ageing = {k: float(row.get(f"range{i + 1}") or 0) for i, k in enumerate(AGEING_RANGES)}
        parties.append({
            "supplier": row.get("party"), "supplier_name": row.get("party_name") or row.get("party"),
            "supplier_group": row.get("supplier_group"),
            "invoiced": round(float(row.get("invoiced") or 0), 2), "paid": round(float(row.get("paid") or 0), 2),
            "outstanding": round(outstanding, 2), "ageing": {k: round(v, 2) for k, v in ageing.items()},
        })
    return _ap_payload(parties)


async def _ap_from_invoices(as_on: date) -> dict[str, Any]:
    c = get_client()
    rows = await c.get_all(
        "Purchase Invoice",
        ["supplier", "supplier_name", "posting_date", "base_grand_total", "outstanding_amount"],
        [["docstatus", "=", 1], ["company", "=", c.company], ["outstanding_amount", "!=", 0],
         ["posting_date", "<=", as_on.isoformat()]],
    )
    df = pd.DataFrame(rows, columns=["supplier", "supplier_name", "posting_date", "base_grand_total", "outstanding_amount"])
    if df.empty:
        return _ap_payload([])
    df["age"] = (pd.Timestamp(as_on) - pd.to_datetime(df["posting_date"])).dt.days.clip(lower=0)
    df["bucket"] = pd.cut(df["age"], bins=[-1, 30, 60, 90, 120, 10**6], labels=AGEING_RANGES)
    df["outstanding_amount"] = df["outstanding_amount"].astype(float)
    parties = []
    for (sup, name), g in df.groupby(["supplier", "supplier_name"]):
        ageing = g.groupby("bucket", observed=False)["outstanding_amount"].sum()
        parties.append({
            "supplier": sup, "supplier_name": name or sup, "supplier_group": None,
            "invoiced": round(float(g["base_grand_total"].astype(float).sum()), 2), "paid": None,
            "outstanding": round(float(g["outstanding_amount"].sum()), 2),
            "ageing": {k: round(float(ageing.get(k, 0.0)), 2) for k in AGEING_RANGES},
        })
    return _ap_payload(parties)


async def payables(rng: DateRange) -> dict[str, Any]:
    """Supplier payables as on the range end date (Accounts Payable Summary -> Purchase Invoice fallback)."""
    c = get_client()
    base = {"range": rng.as_dict(), "as_on": rng.end.isoformat(), "currency": "PKR"}
    try:
        report = await c.run_report("Accounts Payable Summary", {
            "company": c.company, "report_date": rng.end.isoformat(),
            "ageing_based_on": "Posting Date", "range": "30, 60, 90, 120",
        })
        return {**base, "source": "erpnext_report", "report": "Accounts Payable Summary", **_parse_ap_report(report)}
    except ERPNextError as exc:
        log.warning("AP Summary report failed (%s); falling back to Purchase Invoice ageing", exc.message)
        data = await _ap_from_invoices(rng.end)
        return {**base, "source": "raw_fallback", "fallback_reason": exc.message, **data}


# ------------------------------------------------------------- purchases
async def purchases_trend(rng: DateRange) -> dict[str, Any]:
    """Purchases (Purchase Invoice) vs sales (Sales Invoice) per day / month."""
    from . import sales as sales_service

    c = get_client()
    rows, sales_t = await asyncio.gather(
        c.get_list(
            "Purchase Invoice",
            ["posting_date", "sum(base_grand_total) as total", "count(name) as invoice_count"],
            [["docstatus", "=", 1], ["company", "=", c.company],
             ["posting_date", ">=", rng.start.isoformat()], ["posting_date", "<=", rng.end.isoformat()]],
            group_by="posting_date", order_by="posting_date asc", limit_page_length=None,
        ),
        sales_service.trend(rng),
    )
    granularity = rng.granularity
    df = pd.DataFrame(rows, columns=["posting_date", "total", "invoice_count"])
    full = pd.date_range(rng.start, rng.end, freq="D")
    if df.empty:
        df = pd.DataFrame({"total": 0.0, "invoice_count": 0}, index=full)
    else:
        df["posting_date"] = pd.to_datetime(df["posting_date"])
        df = df.set_index("posting_date").reindex(full, fill_value=0)
    df = df.rename_axis("period").reset_index()
    if granularity == "month":
        df = df.groupby(df["period"].dt.to_period("M")).agg({"total": "sum", "invoice_count": "sum"}).reset_index()
        df["period"] = df["period"].dt.to_timestamp()
    sales_by_period = {p["period"]: p["total"] for p in sales_t["points"]}
    points = []
    for p, t, n in zip(df["period"], df["total"], df["invoice_count"]):
        key = p.strftime("%Y-%m-%d")
        points.append({"period": key, "purchases": round(float(t), 2), "purchase_count": int(n),
                       "sales": round(float(sales_by_period.get(key, 0.0)), 2)})
    total_p = sum(p["purchases"] for p in points)
    total_s = sum(p["sales"] for p in points)
    return {
        "source": "sales_invoice", "range": rng.as_dict(), "granularity": granularity, "points": points,
        "total_purchases": round(total_p, 2), "total_sales": round(total_s, 2),
        "purchase_count": int(df["invoice_count"].sum()),
        "purchase_to_sales_pct": round(total_p / total_s * 100, 1) if total_s else None,
    }


# --------------------------------------------------------------- cash flow
async def cash_flow(rng: DateRange) -> dict[str, Any]:
    """Money actually entering / leaving cash & bank accounts per day (or month).

    Internal transfers (cash -> bank etc.) hit two cash/bank accounts in the same
    voucher; they are netted out per voucher so only external flows remain.
    """
    c = get_client()
    accounts = await account_map()
    names = [a["name"] for a in _cash_bank_accounts(accounts)]
    granularity = rng.granularity
    base = {"source": "gl_entry", "range": rng.as_dict(), "granularity": granularity}
    if not names:
        return {**base, "points": [], "total_inflow": 0.0, "total_outflow": 0.0, "net": 0.0, "opening": 0.0, "closing": 0.0}
    rows, before = await asyncio.gather(
        c.get_list(
            "GL Entry", ["posting_date", "voucher_no", "sum(debit) as debit", "sum(credit) as credit"],
            [["is_cancelled", "=", 0], ["company", "=", c.company], ["account", "in", names],
             ["posting_date", ">=", rng.start.isoformat()], ["posting_date", "<=", rng.end.isoformat()]],
            group_by="posting_date, voucher_no", order_by="posting_date asc", limit_page_length=None,
        ),
        c.get_list(
            "GL Entry", ["sum(debit) as debit", "sum(credit) as credit"],
            [["is_cancelled", "=", 0], ["company", "=", c.company], ["account", "in", names],
             ["posting_date", "<", rng.start.isoformat()]],
            limit_page_length=1,
        ),
    )
    b = before[0] if before else {}
    opening = float(b.get("debit") or 0) - float(b.get("credit") or 0)
    df = pd.DataFrame(rows, columns=["posting_date", "voucher_no", "debit", "credit"])
    full = pd.date_range(rng.start, rng.end, freq="D")
    if df.empty:
        daily = pd.DataFrame({"inflow": 0.0, "outflow": 0.0}, index=full)
    else:
        df["debit"] = df["debit"].astype(float)
        df["credit"] = df["credit"].astype(float)
        transfer = df[["debit", "credit"]].min(axis=1)
        df["inflow"] = df["debit"] - transfer
        df["outflow"] = df["credit"] - transfer
        df["posting_date"] = pd.to_datetime(df["posting_date"])
        daily = df.groupby("posting_date")[["inflow", "outflow"]].sum().reindex(full, fill_value=0.0)
    daily = daily.rename_axis("period")
    if granularity == "month":
        daily = daily.groupby(daily.index.to_period("M")).sum()
        daily.index = daily.index.to_timestamp()
    daily["net"] = daily["inflow"] - daily["outflow"]
    daily["balance"] = opening + daily["net"].cumsum()
    points = [
        {"period": p.strftime("%Y-%m-%d"), "inflow": round(float(i), 2), "outflow": round(float(o), 2),
         "net": round(float(n), 2), "balance": round(float(bal), 2)}
        for p, i, o, n, bal in zip(daily.index, daily["inflow"], daily["outflow"], daily["net"], daily["balance"])
    ]
    total_in = float(daily["inflow"].sum())
    total_out = float(daily["outflow"].sum())
    return {
        **base, "points": points, "total_inflow": round(total_in, 2), "total_outflow": round(total_out, 2),
        "net": round(total_in - total_out, 2), "opening": round(opening, 2), "closing": round(opening + total_in - total_out, 2),
    }


# ------------------------------------------------------------ expense trend
async def expense_trend(rng: DateRange, top: int = 5) -> dict[str, Any]:
    """Expenses per period stacked by account group (top N groups + Other)."""
    c = get_client()
    accounts = await account_map()
    exp_accounts = [n for n, a in accounts.items() if a.get("root_type") == "Expense" and not a.get("is_group")]
    granularity = rng.granularity
    base = {"source": "gl_entry", "range": rng.as_dict(), "granularity": granularity}
    if not exp_accounts:
        return {**base, "groups": [], "points": [], "totals": []}
    rows = await c.get_list(
        "GL Entry", ["posting_date", "account", "sum(debit) as debit", "sum(credit) as credit"],
        [["is_cancelled", "=", 0], ["company", "=", c.company], ["account", "in", exp_accounts],
         ["posting_date", ">=", rng.start.isoformat()], ["posting_date", "<=", rng.end.isoformat()]],
        group_by="posting_date, account", order_by="posting_date asc", limit_page_length=None,
    )
    df = pd.DataFrame(rows, columns=["posting_date", "account", "debit", "credit"])
    if df.empty:
        return {**base, "groups": [], "points": [], "totals": []}
    df["amount"] = df["debit"].astype(float) - df["credit"].astype(float)
    df["group"] = df["account"].map(lambda a: _clean(accounts.get(a, {}).get("parent_account")) or "Other")
    df["posting_date"] = pd.to_datetime(df["posting_date"])
    ranked = df.groupby("group")["amount"].sum().sort_values(ascending=False)
    keep = list(ranked.index[:top])
    df["group"] = df["group"].where(df["group"].isin(keep), "Other")
    groups = keep + (["Other"] if (df["group"] == "Other").any() else [])
    pivot = df.pivot_table(index="posting_date", columns="group", values="amount", aggfunc="sum", fill_value=0.0)
    pivot = pivot.reindex(pd.date_range(rng.start, rng.end, freq="D"), fill_value=0.0)
    if granularity == "month":
        pivot = pivot.groupby(pivot.index.to_period("M")).sum()
        pivot.index = pivot.index.to_timestamp()
    for g in groups:
        if g not in pivot.columns:
            pivot[g] = 0.0
    points = [
        {"period": p.strftime("%Y-%m-%d"), **{g: round(float(row[g]), 2) for g in groups},
         "total": round(float(sum(row[g] for g in groups)), 2)}
        for p, row in pivot.iterrows()
    ]
    totals = [{"group": g, "amount": round(float(pivot[g].sum()), 2)} for g in groups]
    return {**base, "groups": groups, "points": points, "totals": totals}


# ------------------------------------------------------------ balance sheet
def _bs_payload(accounts: dict[str, dict[str, Any]], balances: dict[str, float]) -> dict[str, Any]:
    """balances: leaf account -> signed balance (assets positive as debit, liabilities/equity positive as credit)."""
    sections: dict[str, list[dict[str, Any]]] = {"Asset": [], "Liability": [], "Equity": []}
    for acc, bal in balances.items():
        root = accounts.get(acc, {}).get("root_type")
        if root not in sections or abs(bal) < 0.005:
            continue
        sections[root].append({"account": acc, "label": _clean(acc), "amount": round(bal, 2),
                               "parent": _clean(accounts[acc].get("parent_account"))})
    for rows in sections.values():
        rows.sort(key=lambda r: abs(r["amount"]), reverse=True)
    assets = sum(r["amount"] for r in sections["Asset"])
    liabilities = sum(r["amount"] for r in sections["Liability"])
    equity = sum(r["amount"] for r in sections["Equity"])
    provisional = assets - liabilities - equity  # unposted P&L for the period (ERPNext shows this line too)
    return {
        "assets": round(assets, 2), "liabilities": round(liabilities, 2), "equity": round(equity, 2),
        "provisional_profit_loss": round(provisional, 2),
        "current_ratio": None,
        "asset_accounts": sections["Asset"], "liability_accounts": sections["Liability"], "equity_accounts": sections["Equity"],
    }


async def balance_sheet(rng: DateRange) -> dict[str, Any]:
    """Assets / liabilities / equity as on the range end (Balance Sheet report -> GL Entry fallback)."""
    c = get_client()
    accounts = await account_map()
    base = {"range": rng.as_dict(), "as_on": rng.end.isoformat(), "currency": "PKR"}
    try:
        report = await c.run_report("Balance Sheet", {
            "company": c.company, "filter_based_on": "Date Range",
            "period_start_date": rng.start.isoformat(), "period_end_date": rng.end.isoformat(),
            "periodicity": "Yearly", "accumulated_values": 1, "include_default_book_entries": 1,
        })
        balances: dict[str, float] = {}
        for row in report.get("result") or []:
            acc = row.get("account") if isinstance(row, dict) else None
            if not acc or row.get("is_group") or acc not in accounts:
                continue
            balances[acc] = float(row.get("total") or 0)
        data = _bs_payload(accounts, balances)
        source = {"source": "erpnext_report", "report": "Balance Sheet"}
    except ERPNextError as exc:
        log.warning("Balance Sheet report failed (%s); falling back to GL Entry sums", exc.message)
        bs_accounts = [n for n, a in accounts.items() if a.get("root_type") in ("Asset", "Liability", "Equity") and not a.get("is_group")]
        rows = await c.get_list(
            "GL Entry", ["account", "sum(debit) as debit", "sum(credit) as credit"],
            [["is_cancelled", "=", 0], ["company", "=", c.company], ["account", "in", bs_accounts],
             ["posting_date", "<=", rng.end.isoformat()]],
            group_by="account", limit_page_length=None,
        )
        balances = {}
        for r in rows:
            d, cr = float(r.get("debit") or 0), float(r.get("credit") or 0)
            balances[r["account"]] = d - cr if accounts[r["account"]]["root_type"] == "Asset" else cr - d
        data = _bs_payload(accounts, balances)
        source = {"source": "raw_fallback", "fallback_reason": exc.message}
    # current ratio: current assets / current liabilities, found by walking each account's ancestors
    def _is_current(account: str) -> bool:
        seen: set[str] = set()
        node = accounts.get(account, {}).get("parent_account")
        while node and node not in seen:
            seen.add(node)
            label = _clean(node).lower()
            if "current" in label:
                return not label.startswith("non")
            node = accounts.get(node, {}).get("parent_account")
        return False

    ca = sum(r["amount"] for r in data["asset_accounts"] if _is_current(r["account"]))
    cl = sum(r["amount"] for r in data["liability_accounts"] if _is_current(r["account"]))
    data["current_assets"] = round(ca, 2)
    data["current_liabilities"] = round(cl, 2)
    data["current_ratio"] = round(ca / cl, 2) if cl else None
    return {**base, **source, **data}
