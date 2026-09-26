"use client";

import { useApi } from "@/hooks/useApi";
import { fmtDate, fmtPeriod, num, pkr } from "@/lib/format";
import type {
  BalanceSheet, CashFlow, CashPosition, ExpenseTrend, InvoicesResponse, Payables, Pnl, PnlTrend, PurchasesTrend, Range, Receivables, WaterfallStep,
} from "@/lib/types";
import Card from "../Card";
import CashCard from "../CashCard";
import InvoicesTable from "../InvoicesTable";
import KpiCard from "../KpiCard";
import AgeingChart from "../charts/AgeingChart";
import CashFlowChart from "../charts/CashFlowChart";
import ColumnChart from "../charts/ColumnChart";
import HorizontalBars from "../charts/HorizontalBars";
import MultiLineChart from "../charts/MultiLineChart";
import PnlTrendChart from "../charts/PnlTrendChart";
import StackedColumns from "../charts/StackedColumns";
import WaterfallChart from "../charts/WaterfallChart";

interface Queries {
  pnl: ReturnType<typeof useApi<Pnl>>;
  receivables: ReturnType<typeof useApi<Receivables>>;
  payables: ReturnType<typeof useApi<Payables>>;
  cash: ReturnType<typeof useApi<CashPosition>>;
}

const th = "py-1.5 font-medium";
const thead = "border-b border-line text-left text-[11px] uppercase tracking-wide text-ink-3";

export function AccountingKpiRow({ pnl, receivables, payables, cash }: Queries) {
  const p = pnl.data;
  const pc = { loading: pnl.loading, refreshing: pnl.refreshing, error: !!pnl.error };
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
      <KpiCard label="Revenue" value={pkr(p?.revenue)} sub={p ? `Source: ${p.source === "erpnext_report" ? "P&L report" : "GL fallback"}` : undefined} {...pc} />
      <KpiCard label="Expenses" value={pkr(p?.expenses)} sub={p && p.revenue ? `${((p.expenses / p.revenue) * 100).toFixed(1)}% of revenue` : undefined} {...pc} />
      <KpiCard label="Net Profit" value={pkr(p?.net_profit)} sub={p && p.margin_pct !== null ? `${p.margin_pct}% margin` : undefined} {...pc} />
      <KpiCard
        label="Receivables"
        value={pkr(receivables.data?.total_outstanding)}
        sub={receivables.data ? `${num(receivables.data.customer_count)} customers · as on ${fmtDate(receivables.data.as_on)}` : undefined}
        loading={receivables.loading}
        refreshing={receivables.refreshing}
        error={!!receivables.error}
      />
      <KpiCard
        label="Payables"
        value={pkr(payables.data?.total_outstanding)}
        sub={payables.data ? `${num(payables.data.supplier_count)} suppliers · as on ${fmtDate(payables.data.as_on)}` : undefined}
        loading={payables.loading}
        refreshing={payables.refreshing}
        error={!!payables.error}
      />
      <KpiCard
        label="Cash & Bank"
        value={pkr(cash.data?.total)}
        sub={cash.data ? `${pkr(cash.data.net_movement, { sign: true })} in range` : undefined}
        loading={cash.loading}
        refreshing={cash.refreshing}
        error={!!cash.error}
      />
    </div>
  );
}

/** Revenue → expense groups → net profit, built from the P&L breakdown. */
function pnlWaterfall(p: Pnl): WaterfallStep[] {
  const byGroup = new Map<string, number>();
  for (const r of p.expense_breakdown) byGroup.set(r.parent || "Other", (byGroup.get(r.parent || "Other") ?? 0) + r.amount);
  const groups = [...byGroup.entries()].sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const head = groups.slice(0, 4);
  const rest = groups.slice(4).reduce((s, [, v]) => s + v, 0);
  const steps: WaterfallStep[] = [{ label: "Revenue", amount: p.revenue, kind: "total" }];
  for (const [g, v] of head) steps.push({ label: g, amount: -v, kind: "delta" });
  if (rest) steps.push({ label: "Other expenses", amount: -rest, kind: "delta" });
  steps.push({ label: "Net Profit", amount: p.net_profit, kind: "total" });
  return steps;
}

export function AccountingCharts({ range, refreshKey, onRetry, pnl, receivables, payables, cash }: Queries & { range: Range; refreshKey: number; onRetry: () => void }) {
  const trend = useApi<PnlTrend>("/api/accounting/pnl-trend", range, refreshKey);
  const expTrend = useApi<ExpenseTrend>("/api/accounting/expense-trend", range, refreshKey);
  const purchases = useApi<PurchasesTrend>("/api/accounting/purchases-trend", range, refreshKey);
  const cashFlow = useApi<CashFlow>("/api/accounting/cash-flow", range, refreshKey);
  const balance = useApi<BalanceSheet>("/api/accounting/balance-sheet", range, refreshKey);

  const expenses = pnl.data?.expense_breakdown ?? [];
  const shown = expenses.slice(0, 10);
  const other = expenses.slice(10).reduce((s, r) => s + r.amount, 0);
  const rows = [...shown.map((r) => ({ label: r.label, value: r.amount, parent: r.parent })), ...(other ? [{ label: "Other", value: other, parent: "" }] : [])];
  const income = pnl.data?.income_breakdown ?? [];

  const cumulative = (() => {
    if (!trend.data) return [];
    let inc = 0, exp = 0;
    return trend.data.points.map((p) => {
      inc += p.income;
      exp += p.expense;
      return { period: p.period, label: fmtPeriod(p.period, trend.data!.granularity), income: inc, expense: exp, net: inc - exp };
    });
  })();
  const periodHead = (g: "day" | "month") => (_: string | number, e?: { payload?: Record<string, unknown> }) =>
    g === "day" ? fmtDate(String(e?.payload?.period)) : String(e?.payload?.label ?? "");

  return (
    <>
      <Card
        title="P&L Trend"
        subtitle={trend.data ? `${trend.data.granularity === "day" ? "Daily" : "Monthly"} income vs expenses from the general ledger` : undefined}
        source={trend.data?.source}
        loading={trend.loading}
        refreshing={trend.refreshing}
        error={trend.error}
        empty={!!trend.data && trend.data.points.every((p) => p.income === 0 && p.expense === 0)}
        onRetry={onRetry}
        className="lg:col-span-2"
      >
        {trend.data && <PnlTrendChart data={trend.data} />}
      </Card>

      <Card
        title="Cumulative P&L"
        subtitle={cumulative.length ? `Running income, expenses and net over the range · ends at ${pkr(cumulative[cumulative.length - 1].net)} net` : undefined}
        source={trend.data?.source}
        loading={trend.loading}
        refreshing={trend.refreshing}
        error={trend.error}
        empty={!!trend.data && trend.data.points.every((p) => p.income === 0 && p.expense === 0)}
        onRetry={onRetry}
      >
        {trend.data && (
          <MultiLineChart
            data={cumulative}
            series={[
              { key: "income", name: "Income", color: "var(--series-1)" },
              { key: "expense", name: "Expenses", color: "var(--series-2)" },
              { key: "net", name: "Net", color: "var(--series-3)" },
            ]}
            labelFormat={periodHead(trend.data.granularity)}
            zeroLine
          />
        )}
      </Card>

      <Card
        title="Profit Bridge"
        subtitle={pnl.data ? `Revenue to net profit by expense group${pnl.data.margin_pct !== null ? ` · ${pnl.data.margin_pct}% margin` : ""}` : undefined}
        source={pnl.data?.source}
        sourceReason={pnl.data?.fallback_reason}
        loading={pnl.loading}
        refreshing={pnl.refreshing}
        error={pnl.error}
        empty={!!pnl.data && pnl.data.revenue === 0 && pnl.data.expenses === 0}
        onRetry={onRetry}
      >
        {pnl.data && <WaterfallChart steps={pnlWaterfall(pnl.data)} />}
      </Card>

      <Card
        title="Revenue by Account"
        subtitle={pnl.data ? `${income.length} income account${income.length === 1 ? "" : "s"} · ${pkr(pnl.data.revenue)} total` : undefined}
        source={pnl.data?.source}
        sourceReason={pnl.data?.fallback_reason}
        loading={pnl.loading}
        refreshing={pnl.refreshing}
        error={pnl.error}
        empty={!!pnl.data && income.length === 0}
        onRetry={onRetry}
      >
        {pnl.data && (
          <HorizontalBars
            rows={income.slice(0, 10).map((r) => ({ label: r.label, value: r.amount, parent: r.parent, share: pnl.data!.revenue ? ((r.amount / pnl.data!.revenue) * 100).toFixed(1) : "0" }))}
            format={(v, e) => `${pkr(v)} · ${e.payload?.share}%${e.payload?.parent ? ` · ${e.payload.parent}` : ""}`}
            seriesName="Income"
          />
        )}
      </Card>

      <Card
        title="Expense Breakdown"
        subtitle={pnl.data ? `${expenses.length} expense accounts · negative bars are credits (e.g. stock adjustments)` : undefined}
        source={pnl.data?.source}
        sourceReason={pnl.data?.fallback_reason}
        loading={pnl.loading}
        refreshing={pnl.refreshing}
        error={pnl.error}
        empty={!!pnl.data && expenses.length === 0}
        onRetry={onRetry}
      >
        {pnl.data && <HorizontalBars rows={rows} color="var(--series-2)" format={(v, e) => `${pkr(v)}${e.payload?.parent ? ` · ${e.payload.parent}` : ""}`} seriesName="Expense" />}
      </Card>

      <Card
        title="Expense Mix Over Time"
        subtitle={expTrend.data ? `${expTrend.data.granularity === "day" ? "Daily" : "Monthly"} expenses stacked by account group (top ${Math.min(5, expTrend.data.groups.length)}${expTrend.data.groups.includes("Other") ? " + other" : ""})` : undefined}
        source={expTrend.data?.source}
        loading={expTrend.loading}
        refreshing={expTrend.refreshing}
        error={expTrend.error}
        empty={!!expTrend.data && expTrend.data.points.length === 0}
        onRetry={onRetry}
        className="lg:col-span-2"
      >
        {expTrend.data && (
          <StackedColumns
            data={expTrend.data.points.map((p) => ({ ...p, label: fmtPeriod(p.period, expTrend.data!.granularity) }))}
            groups={expTrend.data.groups}
            labelFormat={periodHead(expTrend.data.granularity)}
          />
        )}
      </Card>

      <Card
        title="Sales vs Purchases"
        subtitle={purchases.data ? `${pkr(purchases.data.total_purchases)} purchased (${num(purchases.data.purchase_count)} bills) vs ${pkr(purchases.data.total_sales)} sold${purchases.data.purchase_to_sales_pct !== null ? ` · ${purchases.data.purchase_to_sales_pct}% of sales` : ""}` : undefined}
        source={purchases.data?.source}
        loading={purchases.loading}
        refreshing={purchases.refreshing}
        error={purchases.error}
        empty={!!purchases.data && purchases.data.total_purchases === 0 && purchases.data.total_sales === 0}
        onRetry={onRetry}
      >
        {purchases.data && (
          <MultiLineChart
            data={purchases.data.points.map((p) => ({ ...p, label: fmtPeriod(p.period, purchases.data!.granularity) }))}
            series={[
              { key: "sales", name: "Sales", color: "var(--series-1)" },
              { key: "purchases", name: "Purchases", color: "var(--series-2)" },
            ]}
            labelFormat={periodHead(purchases.data.granularity)}
          />
        )}
      </Card>

      <Card
        title="Cash Flow"
        subtitle={cashFlow.data ? `In ${pkr(cashFlow.data.total_inflow)} · out ${pkr(cashFlow.data.total_outflow)} · net ${pkr(cashFlow.data.net, { sign: true })} · internal transfers excluded` : undefined}
        source={cashFlow.data?.source}
        loading={cashFlow.loading}
        refreshing={cashFlow.refreshing}
        error={cashFlow.error}
        empty={!!cashFlow.data && cashFlow.data.points.every((p) => p.inflow === 0 && p.outflow === 0)}
        onRetry={onRetry}
        height={300}
      >
        {cashFlow.data && <CashFlowChart data={cashFlow.data} />}
      </Card>

      <Card
        title="Receivables Ageing"
        subtitle={receivables.data ? `${pkr(receivables.data.total_outstanding)} outstanding as on ${fmtDate(receivables.data.as_on)}` : undefined}
        source={receivables.data?.source}
        sourceReason={receivables.data?.fallback_reason}
        loading={receivables.loading}
        refreshing={receivables.refreshing}
        error={receivables.error}
        empty={!!receivables.data && receivables.data.total_outstanding === 0}
        emptyHint="All customer invoices are fully paid"
        onRetry={onRetry}
      >
        {receivables.data && (
          <div className="flex flex-col gap-3">
            <AgeingChart buckets={receivables.data.ageing} height={200} />
            {receivables.data.top_customers.length > 0 && (
              <table className="w-full text-xs">
                <thead>
                  <tr className={thead}>
                    <th className={th}>Customer</th>
                    <th className={`${th} text-right`}>Invoiced</th>
                    <th className={`${th} text-right`}>Outstanding</th>
                  </tr>
                </thead>
                <tbody className="tnum">
                  {receivables.data.top_customers.slice(0, 5).map((c) => (
                    <tr key={c.customer} className="border-b border-line/60">
                      <td className="py-1.5 text-ink">{c.customer_name}</td>
                      <td className="py-1.5 text-right text-ink-2">{pkr(c.invoiced)}</td>
                      <td className="py-1.5 text-right font-medium text-ink">{pkr(c.outstanding)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Card>

      <Card
        title="Payables Ageing"
        subtitle={payables.data ? `${pkr(payables.data.total_outstanding)} owed to ${num(payables.data.supplier_count)} suppliers as on ${fmtDate(payables.data.as_on)}` : undefined}
        source={payables.data?.source}
        sourceReason={payables.data?.fallback_reason}
        loading={payables.loading}
        refreshing={payables.refreshing}
        error={payables.error}
        empty={!!payables.data && payables.data.total_outstanding === 0 && payables.data.top_suppliers.length === 0}
        emptyHint="All supplier bills are fully paid"
        onRetry={onRetry}
      >
        {payables.data && (
          <div className="flex flex-col gap-3">
            <AgeingChart buckets={payables.data.ageing} seriesName="Payable" height={200} />
            {payables.data.top_suppliers.length > 0 && (
              <table className="w-full text-xs">
                <thead>
                  <tr className={thead}>
                    <th className={th}>Supplier</th>
                    <th className={`${th} text-right`}>Invoiced</th>
                    <th className={`${th} text-right`}>Paid</th>
                    <th className={`${th} text-right`}>Outstanding</th>
                  </tr>
                </thead>
                <tbody className="tnum">
                  {payables.data.top_suppliers.slice(0, 6).map((s) => (
                    <tr key={s.supplier} className="border-b border-line/60">
                      <td className="py-1.5 text-ink" title={s.supplier_group ?? undefined}>{s.supplier_name}</td>
                      <td className="py-1.5 text-right text-ink-2">{pkr(s.invoiced)}</td>
                      <td className="py-1.5 text-right text-ink-2">{s.paid === null ? "—" : pkr(s.paid)}</td>
                      <td className="py-1.5 text-right font-medium text-ink">{pkr(s.outstanding)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Card>

      <CashCard state={cash} onRetry={onRetry} />

      <Card
        title="Balance Sheet"
        subtitle={balance.data ? `As on ${fmtDate(balance.data.as_on)}${balance.data.current_ratio !== null ? ` · current ratio ${num(balance.data.current_ratio, 2)}` : ""} · provisional P&L ${pkr(balance.data.provisional_profit_loss, { sign: true })}` : undefined}
        source={balance.data?.source}
        sourceReason={balance.data?.fallback_reason}
        loading={balance.loading}
        refreshing={balance.refreshing}
        error={balance.error}
        empty={!!balance.data && balance.data.assets === 0 && balance.data.liabilities === 0}
        onRetry={onRetry}
      >
        {balance.data && (
          <div className="flex flex-col gap-3">
            <ColumnChart
              rows={[
                { label: "Assets", value: balance.data.assets },
                { label: "Liabilities", value: balance.data.liabilities },
                { label: "Equity", value: balance.data.equity },
                { label: "Provisional P&L", value: balance.data.provisional_profit_loss },
              ]}
              colors={["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--ink-3)"]}
              format={(v) => pkr(v)}
              height={180}
            />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <AccountList title="Top assets" rows={balance.data.asset_accounts.slice(0, 5)} />
              <AccountList title="Top liabilities" rows={balance.data.liability_accounts.slice(0, 5)} />
            </div>
          </div>
        )}
      </Card>
    </>
  );
}

function AccountList({ title, rows }: { title: string; rows: { account: string; label: string; amount: number; parent: string }[] }) {
  return (
    <table className="w-full self-start text-xs">
      <thead>
        <tr className={thead}>
          <th className={th}>{title}</th>
          <th className={`${th} text-right`}>Balance</th>
        </tr>
      </thead>
      <tbody className="tnum">
        {rows.length === 0 && (
          <tr>
            <td colSpan={2} className="py-1.5 text-ink-3">None</td>
          </tr>
        )}
        {rows.map((r) => (
          <tr key={r.account} className="border-b border-line/60">
            <td className="py-1.5 text-ink" title={r.parent}>{r.label}</td>
            <td className="py-1.5 text-right font-medium text-ink">{pkr(r.amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function AccountingTab({ range, refreshKey, onRetry }: { range: Range; refreshKey: number; onRetry: () => void }) {
  const pnl = useApi<Pnl>("/api/accounting/pnl", range, refreshKey);
  const receivables = useApi<Receivables>("/api/accounting/receivables", range, refreshKey);
  const payables = useApi<Payables>("/api/accounting/payables", range, refreshKey);
  const cash = useApi<CashPosition>("/api/accounting/cash-position", range, refreshKey);
  const invoices = useApi<InvoicesResponse>("/api/sales/invoices", range, refreshKey);
  return (
    <div className="flex flex-col gap-4">
      <AccountingKpiRow pnl={pnl} receivables={receivables} payables={payables} cash={cash} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AccountingCharts range={range} refreshKey={refreshKey} onRetry={onRetry} pnl={pnl} receivables={receivables} payables={payables} cash={cash} />
      </div>
      <InvoicesTable state={invoices} range={range} onRetry={onRetry} />
    </div>
  );
}
