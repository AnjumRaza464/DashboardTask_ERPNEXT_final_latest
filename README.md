# Sindh Bakery — Sales & Accounting Dashboard

Live sales and accounting dashboard for the **Sindh Bakery** company on ERPNext
(`https://erp.bnbcloudservices.com`). Currency: PKR.

```
backend/   FastAPI proxy in front of the ERPNext REST API (holds the API key/secret)
api/       Vercel entry point (api/index.py) that serves the same FastAPI app
src/       Next.js (App Router) + Tailwind CSS + Recharts dashboard (repo root is the Next.js app)
```

The browser only ever talks to the FastAPI backend. ERPNext credentials live in
`backend/.env` and are never sent to the frontend.

## Run (local / office use, no login)

Backend (port **8000**):

```powershell
cd backend
python -m venv .venv            # first time only
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then fill in ERPNEXT_API_KEY / ERPNEXT_API_SECRET
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Frontend (port **3000**, run from the repo root):

```powershell
npm install                     # first time only
npm run dev                     # or: npm run build && npm run start
```

Open http://localhost:3000. In development `next.config.ts` proxies `/api/*` to the
FastAPI server (`BACKEND_URL` in `.env.local`, default `http://127.0.0.1:8000`), so the
browser only ever talks to one origin.

## Deploy (Vercel)

The repo deploys as a single Vercel project: the Next.js app at the root plus the
FastAPI backend as a Python serverless function (`api/index.py`, routed via
`vercel.json`, dependencies from `requirements.txt`). Set these environment
variables in the Vercel project (same names as `backend/.env.example`):

`ERPNEXT_URL`, `ERPNEXT_API_KEY`, `ERPNEXT_API_SECRET`, `ERPNEXT_COMPANY`,
`CACHE_TTL_SECONDS` (optional). `FRONTEND_ORIGINS` is not needed on Vercel because
frontend and API share one origin.

## Backend API

All endpoints accept `start` and `end` (`YYYY-MM-DD`, default = current month to
today) and `refresh=1` to bypass the 2-minute in-memory cache.

| Endpoint | Data | Source |
|---|---|---|
| `GET /api/health` | ERPNext connectivity check | — |
| `GET /api/sales/kpis` | total sales, invoice count, avg invoice, outstanding, deltas vs previous period | Sales Invoice |
| `GET /api/sales/invoices` | all submitted invoices in range (table / CSV) | Sales Invoice |
| `GET /api/sales/trend` | daily (≤92 days) or monthly sales | Sales Invoice |
| `GET /api/sales/top-items?limit=10` | top items by value | Sales Invoice Item (`parent` param) |
| `GET /api/sales/by-outlet` | sales per cost centre / POS profile | Sales Invoice |
| `GET /api/accounting/pnl` | revenue, expenses, net profit, breakdowns | **Profit and Loss Statement** report → GL Entry fallback |
| `GET /api/accounting/pnl-trend` | daily/monthly income vs expense | GL Entry aggregates |
| `GET /api/accounting/receivables` | outstanding, ageing buckets, top customers (as on `end`) | **Accounts Receivable Summary** report → Sales Invoice fallback |
| `GET /api/accounting/cash-position` | cash & bank balances as on `end`, movement in range | `get_balance_on` API → GL Entry fallback |
| `GET /api/sales/compare` | current period vs the previous same-length period, aligned by day/month | Sales Invoice |
| `GET /api/sales/by-item-group` | sales value, qty and item count per item group | Sales Invoice Item |
| `GET /api/sales/by-hour` | sales per hour of day, peak hour, average per trading day | Sales Invoice (`posting_time`) |
| `GET /api/sales/by-weekday` | total and average sales per weekday | Sales Invoice |
| `GET /api/sales/invoice-distribution` | invoice value histogram + median / mean / p90 | Sales Invoice |
| `GET /api/sales/top-customers?limit=10` | top customers by value, invoices, outstanding, last invoice | Sales Invoice |
| `GET /api/sales/payment-modes` | Cash / Card / … split of settled sales, plus credit remainder | Sales Invoice Payment |
| `GET /api/sales/composition` | gross → discounts → taxes → returns → net (waterfall) | Sales Invoice |
| `GET /api/accounting/payables` | supplier outstanding, ageing buckets, top suppliers (as on `end`) | **Accounts Payable Summary** report → Purchase Invoice fallback |
| `GET /api/accounting/purchases-trend` | daily/monthly purchases vs sales | Purchase Invoice + Sales Invoice |
| `GET /api/accounting/cash-flow` | inflow / outflow / running balance of cash & bank accounts (internal transfers netted per voucher) | GL Entry |
| `GET /api/accounting/expense-trend` | daily/monthly expenses stacked by account group (top 5 + other) | GL Entry |
| `GET /api/accounting/balance-sheet` | assets, liabilities, equity, provisional P&L, current ratio, top accounts | **Balance Sheet** report → GL Entry fallback |
| `GET /api/summary` | everything above for the All tab in one call | mixed |
| `POST /api/cache/clear` | drop the cache | — |

Every accounting payload carries `source`: `erpnext_report`, `erpnext_api`,
`gl_entry` or `raw_fallback` (with `fallback_reason`). The UI shows this as a
badge on each card.

Interactive docs: http://localhost:8000/docs

## Notes on this ERPNext instance (verified 23 Sep 2026)

- One company (`Sindh Bakery`, abbr `SB`), fiscal year 2026, 121 submitted POS
  invoices from 16 Apr 2026, all paid (receivables are currently zero).
- One outlet: cost centre `outlet-1 (SB) - SB`, POS profile
  `POS-(Outlet-1-WW)-SB-Casher-1`. More outlets appear automatically once they
  have their own cost centre / POS profile.
- Several **expense** accounts are typed `account_type = Cash` in the chart of
  accounts. Cash & Bank position therefore filters on `root_type = Asset` as
  well, so only `Cash - SB` and `Bank Account - SB` are counted.
- `Stock Adjustment - SB` carries large credit balances, so it shows as a
  negative expense in the breakdown (this matches ERPNext's own P&L report).
