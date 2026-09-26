"use client";

import { useApi } from "@/hooks/useApi";
import { fmtDate, fmtPeriod, fmtRange, num, pct, pkr } from "@/lib/format";
import type {
  HourlySales, InvoiceDistribution, InvoicesResponse, ItemGroupSales, OutletSales, PaymentModes, Range, SalesCompare,
  SalesComposition, SalesKpis, SalesTrend, TopCustomers, TopItems, WeekdaySales,
} from "@/lib/types";
import Card from "../Card";
import InvoicesTable from "../InvoicesTable";
import KpiCard from "../KpiCard";
import ColumnChart from "../charts/ColumnChart";
import HorizontalBars from "../charts/HorizontalBars";
import MultiLineChart from "../charts/MultiLineChart";
import SalesTrendChart from "../charts/SalesTrendChart";
import ShareBar from "../charts/ShareBar";
import WaterfallChart from "../charts/WaterfallChart";

export function SalesKpiRow({ kpis }: { kpis: ReturnType<typeof useApi<SalesKpis>> }) {
  const c = kpis.data?.current;
  const d = kpis.data?.delta_pct;
  const prev = kpis.data ? fmtRange(kpis.data.previous_range.start, kpis.data.previous_range.end) : undefined;
  const common = { loading: kpis.loading, refreshing: kpis.refreshing, error: !!kpis.error };
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <KpiCard label="Total Sales" value={pkr(c?.total_sales)} delta={d?.total_sales} sub={prev && `vs ${prev}`} {...common} />
      <KpiCard label="Invoice Count" value={num(c?.invoice_count)} delta={d?.invoice_count} sub={c && c.return_count ? `${c.return_count} returns` : undefined} {...common} />
      <KpiCard label="Avg Invoice Value" value={pkr(c?.avg_invoice_value)} delta={d?.avg_invoice_value} {...common} />
      <KpiCard label="Qty Sold" value={num(c?.total_qty)} delta={d?.total_qty} sub={c && c.invoice_count ? `${num(c.total_qty / c.invoice_count, 1)} per invoice` : undefined} {...common} />
      <KpiCard label="Outstanding" value={pkr(c?.outstanding)} delta={d?.outstanding} invert sub={c ? "on invoices in range" : undefined} {...common} />
    </div>
  );
}

const th = "py-1.5 font-medium";
const thead = "border-b border-line text-left text-[11px] uppercase tracking-wide text-ink-3";

export function SalesCharts({ range, refreshKey, onRetry }: { range: Range; refreshKey: number; onRetry: () => void }) {
  const trend = useApi<SalesTrend>("/api/sales/trend", range, refreshKey);
  const compare = useApi<SalesCompare>("/api/sales/compare", range, refreshKey);
  const items = useApi<TopItems>("/api/sales/top-items", range, refreshKey, { limit: 10 });
  const outlets = useApi<OutletSales>("/api/sales/by-outlet", range, refreshKey);
  const groups = useApi<ItemGroupSales>("/api/sales/by-item-group", range, refreshKey);
  const modes = useApi<PaymentModes>("/api/sales/payment-modes", range, refreshKey);
  const hours = useApi<HourlySales>("/api/sales/by-hour", range, refreshKey);
  const weekdays = useApi<WeekdaySales>("/api/sales/by-weekday", range, refreshKey);
  const dist = useApi<InvoiceDistribution>("/api/sales/invoice-distribution", range, refreshKey);
  const composition = useApi<SalesComposition>("/api/sales/composition", range, refreshKey);
  const customers = useApi<TopCustomers>("/api/sales/top-customers", range, refreshKey, { limit: 10 });

  const compareRows = compare.data
    ? compare.data.points.map((p) => ({
        ...p,
        label: p.period ? fmtPeriod(p.period, compare.data!.granularity) : `#${p.index}`,
      }))
    : [];

  return (
    <>
      <Card
        title="Sales Trend"
        subtitle={trend.data ? (trend.data.granularity === "day" ? "Daily invoiced sales (PKR)" : "Monthly invoiced sales (PKR)") : undefined}
        source={trend.data?.source}
        loading={trend.loading}
        refreshing={trend.refreshing}
        error={trend.error}
        empty={!!trend.data && trend.data.points.every((p) => p.total === 0)}
        onRetry={onRetry}
        className="lg:col-span-2"
      >
        {trend.data && <SalesTrendChart data={trend.data} />}
      </Card>

      <Card
        title="Sales vs Previous Period"
        subtitle={
          compare.data
            ? `${pkr(compare.data.current_total)} vs ${pkr(compare.data.previous_total)} (${fmtRange(compare.data.previous_range.start, compare.data.previous_range.end)})${compare.data.delta_pct !== null ? ` · ${pct(compare.data.delta_pct)}` : ""}`
            : undefined
        }
        source={compare.data?.source}
        loading={compare.loading}
        refreshing={compare.refreshing}
        error={compare.error}
        empty={!!compare.data && compare.data.current_total === 0 && compare.data.previous_total === 0}
        onRetry={onRetry}
        className="lg:col-span-2"
      >
        {compare.data && (
          <MultiLineChart
            data={compareRows}
            series={[
              { key: "current", name: "This period", color: "var(--series-1)" },
              { key: "previous", name: "Previous period", color: "var(--ink-3)", dashed: true },
            ]}
            labelFormat={(_, e) => {
              const p = e?.payload as { period?: string | null; previous_period?: string | null; label?: string } | undefined;
              if (compare.data!.granularity === "day") return `${fmtDate(p?.period)} vs ${fmtDate(p?.previous_period)}`;
              return `${p?.label ?? ""} vs ${p?.previous_period ? fmtPeriod(p.previous_period, "month") : "—"}`;
            }}
          />
        )}
      </Card>

      <Card
        title="Top Items"
        subtitle={items.data ? `Top ${items.data.items.length} of ${items.data.distinct_items} items by sales value` : undefined}
        source={items.data?.source}
        loading={items.loading}
        refreshing={items.refreshing}
        error={items.error}
        empty={!!items.data && items.data.items.length === 0}
        onRetry={onRetry}
      >
        {items.data && (
          <HorizontalBars
            rows={items.data.items.map((i) => ({ label: i.item_name, value: i.amount, qty: i.qty, share: i.share_pct }))}
            format={(v, e) => `${pkr(v)} · ${num(Number(e.payload?.qty), 2)} qty · ${e.payload?.share}%`}
            seriesName="Sales"
          />
        )}
      </Card>

      <Card
        title="Outlet-wise Sales"
        subtitle={outlets.data ? `${outlets.data.outlets.length} outlet${outlets.data.outlets.length === 1 ? "" : "s"} · ${pkr(outlets.data.total)} total` : undefined}
        source={outlets.data?.source}
        loading={outlets.loading}
        refreshing={outlets.refreshing}
        error={outlets.error}
        empty={!!outlets.data && outlets.data.outlets.length === 0}
        onRetry={onRetry}
      >
        {outlets.data && (
          <div className="flex h-full flex-col gap-3">
            <HorizontalBars
              rows={outlets.data.outlets.map((o) => ({ label: o.outlet, value: o.total, count: o.invoice_count, share: o.share_pct }))}
              format={(v, e) => `${pkr(v)} · ${e.payload?.count} inv · ${e.payload?.share}%`}
              height={Math.max(120, outlets.data.outlets.length * 36 + 30)}
              seriesName="Sales"
            />
            <table className="w-full text-xs">
              <thead>
                <tr className={thead}>
                  <th className={th}>Outlet</th>
                  <th className={`${th} text-right`}>Invoices</th>
                  <th className={`${th} text-right`}>Avg Invoice</th>
                  <th className={`${th} text-right`}>Sales</th>
                  <th className={`${th} text-right`}>Share</th>
                </tr>
              </thead>
              <tbody className="tnum">
                {outlets.data.outlets.map((o) => (
                  <tr key={o.outlet + (o.pos_profile ?? "")} className="border-b border-line/60">
                    <td className="py-1.5 text-ink" title={o.pos_profile ?? undefined}>{o.outlet}</td>
                    <td className="py-1.5 text-right text-ink-2">{num(o.invoice_count)}</td>
                    <td className="py-1.5 text-right text-ink-2">{pkr(o.avg_invoice_value)}</td>
                    <td className="py-1.5 text-right font-medium text-ink">{pkr(o.total)}</td>
                    <td className="py-1.5 text-right text-ink-2">{o.share_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card
        title="Sales by Item Group"
        subtitle={groups.data ? `${groups.data.groups.length} groups · ${pkr(groups.data.total_amount)} total` : undefined}
        source={groups.data?.source}
        loading={groups.loading}
        refreshing={groups.refreshing}
        error={groups.error}
        empty={!!groups.data && groups.data.groups.length === 0}
        onRetry={onRetry}
        height={200}
      >
        {groups.data && (
          <ShareBar
            rows={groups.data.groups.map((g) => ({ label: g.item_group, value: g.amount, note: `${num(g.items)} items · ${num(g.qty)} qty` }))}
            total={groups.data.total_amount}
          />
        )}
      </Card>

      <Card
        title="Payment Modes"
        subtitle={modes.data ? `How ${pkr(modes.data.total)} of invoiced sales was settled` : undefined}
        source={modes.data?.source}
        loading={modes.loading}
        refreshing={modes.refreshing}
        error={modes.error}
        empty={!!modes.data && modes.data.modes.length === 0}
        onRetry={onRetry}
        height={200}
      >
        {modes.data && (
          <ShareBar rows={modes.data.modes.map((m) => ({ label: m.mode, value: m.amount, note: `${num(m.count)} inv` }))} total={modes.data.total} />
        )}
      </Card>

      <Card
        title="Sales by Hour of Day"
        subtitle={hours.data ? `Total sales per hour across ${num(hours.data.active_days)} trading days${hours.data.peak_hour !== null ? ` · peak ${String(hours.data.peak_hour).padStart(2, "0")}:00` : ""}` : undefined}
        source={hours.data?.source}
        loading={hours.loading}
        refreshing={hours.refreshing}
        error={hours.error}
        empty={!!hours.data && hours.data.points.every((p) => p.total === 0)}
        onRetry={onRetry}
      >
        {hours.data && (
          <ColumnChart
            rows={hours.data.points.map((p) => ({ label: p.label, value: p.total, count: p.invoice_count, avg: p.avg_per_day, hour: p.hour }))}
            format={(v, e) => `${pkr(v)} · ${e.payload?.count} inv · ${pkr(Number(e.payload?.avg))}/day`}
            seriesName="Sales"
            tickEvery={3}
            highlight={(r) => r.hour === hours.data!.peak_hour}
          />
        )}
      </Card>

      <Card
        title="Sales by Weekday"
        subtitle={weekdays.data ? `Average sales per day of the week${weekdays.data.best_weekday ? ` · best ${weekdays.data.best_weekday}` : ""}` : undefined}
        source={weekdays.data?.source}
        loading={weekdays.loading}
        refreshing={weekdays.refreshing}
        error={weekdays.error}
        empty={!!weekdays.data && weekdays.data.points.every((p) => p.total === 0)}
        onRetry={onRetry}
      >
        {weekdays.data && (
          <ColumnChart
            rows={weekdays.data.points.map((p) => ({ label: p.weekday, value: p.avg_per_day, total: p.total, count: p.invoice_count, occ: p.occurrences }))}
            format={(v, e) => `${pkr(v)}/day · ${pkr(Number(e.payload?.total))} over ${e.payload?.occ} days · ${e.payload?.count} inv`}
            seriesName="Avg / day"
            highlight={(r) => r.label === weekdays.data!.best_weekday}
          />
        )}
      </Card>

      <Card
        title="Invoice Value Distribution"
        subtitle={dist.data ? `${num(dist.data.stats.count)} invoices · median ${pkr(dist.data.stats.median)} · 90% under ${pkr(dist.data.stats.p90)} · max ${pkr(dist.data.stats.max)}` : undefined}
        source={dist.data?.source}
        loading={dist.loading}
        refreshing={dist.refreshing}
        error={dist.error}
        empty={!!dist.data && dist.data.stats.count === 0}
        onRetry={onRetry}
      >
        {dist.data && (
          <ColumnChart
            rows={dist.data.buckets.map((b) => ({ label: b.bucket, value: b.invoice_count, total: b.total }))}
            format={(v, e) => `${num(v)} invoices · ${pkr(Number(e.payload?.total))}`}
            seriesName="Invoices"
            ordinal
            yFormat={(v) => num(v)}
          />
        )}
      </Card>

      <Card
        title="Sales Composition"
        subtitle={composition.data ? `Gross to net · ${num(composition.data.invoice_count)} invoices · discounts ${composition.data.discount_pct}% of gross${composition.data.return_count ? ` · ${composition.data.return_count} returns` : ""}` : undefined}
        source={composition.data?.source}
        loading={composition.loading}
        refreshing={composition.refreshing}
        error={composition.error}
        empty={!!composition.data && composition.data.gross === 0}
        onRetry={onRetry}
      >
        {composition.data && <WaterfallChart steps={composition.data.steps} />}
      </Card>

      <Card
        title="Top Customers"
        subtitle={customers.data ? `Top ${customers.data.customers.length} of ${num(customers.data.distinct_customers)} customers by sales value` : undefined}
        source={customers.data?.source}
        loading={customers.loading}
        refreshing={customers.refreshing}
        error={customers.error}
        empty={!!customers.data && customers.data.customers.length === 0}
        onRetry={onRetry}
        className="lg:col-span-2"
      >
        {customers.data && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <HorizontalBars
              rows={customers.data.customers.map((c) => ({ label: c.customer_name, value: c.total, count: c.invoice_count, share: c.share_pct }))}
              format={(v, e) => `${pkr(v)} · ${e.payload?.count} inv · ${e.payload?.share}%`}
              seriesName="Sales"
              height={Math.max(160, customers.data.customers.length * 30 + 24)}
            />
            <table className="w-full self-start text-xs">
              <thead>
                <tr className={thead}>
                  <th className={th}>Customer</th>
                  <th className={`${th} text-right`}>Invoices</th>
                  <th className={`${th} text-right`}>Avg Invoice</th>
                  <th className={`${th} text-right`}>Sales</th>
                  <th className={`${th} text-right`}>Outstanding</th>
                  <th className={`${th} text-right`}>Last</th>
                </tr>
              </thead>
              <tbody className="tnum">
                {customers.data.customers.map((c) => (
                  <tr key={c.customer} className="border-b border-line/60">
                    <td className="py-1.5 text-ink">{c.customer_name}</td>
                    <td className="py-1.5 text-right text-ink-2">{num(c.invoice_count)}</td>
                    <td className="py-1.5 text-right text-ink-2">{pkr(c.avg_invoice_value)}</td>
                    <td className="py-1.5 text-right font-medium text-ink">{pkr(c.total)}</td>
                    <td className={`py-1.5 text-right ${c.outstanding > 0 ? "text-warn" : "text-ink-2"}`}>{pkr(c.outstanding)}</td>
                    <td className="py-1.5 text-right text-ink-2">{fmtDate(c.last_invoice)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

export default function SalesTab({ range, refreshKey, onRetry }: { range: Range; refreshKey: number; onRetry: () => void }) {
  const kpis = useApi<SalesKpis>("/api/sales/kpis", range, refreshKey);
  const invoices = useApi<InvoicesResponse>("/api/sales/invoices", range, refreshKey);
  return (
    <div className="flex flex-col gap-4">
      <SalesKpiRow kpis={kpis} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SalesCharts range={range} refreshKey={refreshKey} onRetry={onRetry} />
      </div>
      <InvoicesTable state={invoices} range={range} onRetry={onRetry} />
    </div>
  );
}
