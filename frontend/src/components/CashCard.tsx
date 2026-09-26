"use client";

import Card from "./Card";
import { fmtDate, pkr } from "@/lib/format";
import type { CashPosition } from "@/lib/types";
import type { QueryState } from "@/hooks/useApi";

export default function CashCard({ state, onRetry }: { state: QueryState<CashPosition>; onRetry?: () => void }) {
  const d = state.data;
  return (
    <Card
      title="Cash & Bank Position"
      subtitle={d ? `Balances as on ${fmtDate(d.as_on)} · movement within range` : "Closing balances of cash and bank accounts"}
      source={d?.source}
      sourceReason={d?.fallback_reason}
      loading={state.loading}
      refreshing={state.refreshing}
      error={state.error}
      empty={!!d && d.accounts.length === 0}
      emptyHint="No Cash/Bank accounts found for the company"
      onRetry={onRetry}
      height={200}
    >
      {d && (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Total" value={pkr(d.total)} strong />
            <Stat label="Cash" value={pkr(d.cash_total)} />
            <Stat label="Bank" value={pkr(d.bank_total)} />
          </div>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-line text-left text-[11px] uppercase tracking-wide text-ink-3">
                <th className="py-1.5 font-medium">Account</th>
                <th className="py-1.5 text-right font-medium">Inflow</th>
                <th className="py-1.5 text-right font-medium">Outflow</th>
                <th className="py-1.5 text-right font-medium">Net</th>
                <th className="py-1.5 text-right font-medium">Balance</th>
              </tr>
            </thead>
            <tbody className="tnum">
              {d.accounts.map((a) => (
                <tr key={a.account} className="border-b border-line/60">
                  <td className="py-1.5 text-ink">
                    {a.label} <span className="text-ink-3">· {a.type}</span>
                  </td>
                  <td className="py-1.5 text-right text-ink-2">{pkr(a.inflow)}</td>
                  <td className="py-1.5 text-right text-ink-2">{pkr(a.outflow)}</td>
                  <td className={`py-1.5 text-right ${a.net_movement > 0 ? "text-good" : a.net_movement < 0 ? "text-bad" : "text-ink-2"}`}>{pkr(a.net_movement, { sign: true })}</td>
                  <td className="py-1.5 text-right font-medium text-ink">{pkr(a.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-lg bg-surface-2 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-ink-3">{label}</div>
      <div className={`truncate ${strong ? "text-lg font-semibold text-ink" : "text-sm font-medium text-ink-2"}`} title={value}>
        {value}
      </div>
    </div>
  );
}
