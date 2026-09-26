"use client";

import { useApi } from "@/hooks/useApi";
import type { CashPosition, InvoicesResponse, Payables, Pnl, Range, Receivables, SalesKpis } from "@/lib/types";
import InvoicesTable from "../InvoicesTable";
import { AccountingCharts, AccountingKpiRow } from "./AccountingTab";
import { SalesCharts, SalesKpiRow } from "./SalesTab";

function SectionHeading({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mt-2 flex items-baseline gap-2">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <span className="text-xs text-ink-3">{hint}</span>
    </div>
  );
}

/** Combined view: both KPI rows, then both chart sets, then the invoices table. */
export default function AllTab({ range, refreshKey, onRetry }: { range: Range; refreshKey: number; onRetry: () => void }) {
  const kpis = useApi<SalesKpis>("/api/sales/kpis", range, refreshKey);
  const pnl = useApi<Pnl>("/api/accounting/pnl", range, refreshKey);
  const receivables = useApi<Receivables>("/api/accounting/receivables", range, refreshKey);
  const payables = useApi<Payables>("/api/accounting/payables", range, refreshKey);
  const cash = useApi<CashPosition>("/api/accounting/cash-position", range, refreshKey);
  const invoices = useApi<InvoicesResponse>("/api/sales/invoices", range, refreshKey);

  return (
    <div className="flex flex-col gap-4">
      <SectionHeading title="Sales" hint="from Sales Invoices" />
      <SalesKpiRow kpis={kpis} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SalesCharts range={range} refreshKey={refreshKey} onRetry={onRetry} />
      </div>
      <SectionHeading title="Accounting" hint="from the ERPNext report engine and general ledger" />
      <AccountingKpiRow pnl={pnl} receivables={receivables} payables={payables} cash={cash} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AccountingCharts range={range} refreshKey={refreshKey} onRetry={onRetry} pnl={pnl} receivables={receivables} payables={payables} cash={cash} />
      </div>
      <InvoicesTable state={invoices} range={range} onRetry={onRetry} />
    </div>
  );
}
