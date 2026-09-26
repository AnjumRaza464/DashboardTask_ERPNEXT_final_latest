"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { compact, fmtDate, fmtPeriod, pkr } from "@/lib/format";
import type { CashFlow } from "@/lib/types";
import ChartTooltip from "./ChartTooltip";

/** Inflows vs outflows per period (columns) with the running cash & bank balance underneath. */
export default function CashFlowChart({ data, height = 300 }: { data: CashFlow; height?: number }) {
  const points = data.points.map((p) => ({ ...p, label: fmtPeriod(p.period, data.granularity) }));
  const tickEvery = Math.max(1, Math.ceil(points.length / 8));
  const head = (label: string | number, e?: { payload?: Record<string, unknown> }) =>
    data.granularity === "day" ? fmtDate(String(e?.payload?.period)) : String(label);
  const balanceNegative = points.some((p) => p.balance < 0);
  const top = Math.round(height * 0.62);
  const bottom = height - top;
  return (
    <div className="flex flex-col">
      <ResponsiveContainer width="100%" height={top}>
        <BarChart data={points} margin={{ top: 8, right: 24, left: 0, bottom: 0 }} barCategoryGap="25%" barGap={2} syncId="cashflow">
          <CartesianGrid vertical={false} strokeWidth={1} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} dy={6} interval={tickEvery - 1} hide />
          <YAxis tickFormatter={(v: number) => compact(v)} tickLine={false} axisLine={false} width={52} />
          <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<ChartTooltip labelFormat={head} format={(v) => pkr(v)} />} />
          <Legend iconType="square" iconSize={10} verticalAlign="top" align="right" wrapperStyle={{ paddingBottom: 6 }} />
          <Bar dataKey="inflow" name="Inflow" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={40} isAnimationActive={false} />
          <Bar dataKey="outflow" name="Outflow" fill="var(--series-2)" radius={[4, 4, 0, 0]} maxBarSize={40} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={bottom}>
        <AreaChart data={points} margin={{ top: 4, right: 24, left: 0, bottom: 0 }} syncId="cashflow">
          <defs>
            <linearGradient id="cashBalanceFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--series-3)" stopOpacity={0.22} />
              <stop offset="100%" stopColor="var(--series-3)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} strokeWidth={1} />
          <XAxis dataKey="label" tickLine={false} axisLine={false} dy={6} interval={tickEvery - 1} />
          <YAxis tickFormatter={(v: number) => compact(v)} tickLine={false} axisLine={false} width={52} />
          {balanceNegative && <ReferenceLine y={0} stroke="var(--axis)" />}
          <Tooltip cursor={{ strokeWidth: 1 }} content={<ChartTooltip noSwatch labelFormat={head} format={(v) => pkr(v)} />} />
          <Area isAnimationActive={false} type="monotone" dataKey="balance" name="Closing balance" stroke="var(--series-3)" strokeWidth={2} fill="url(#cashBalanceFill)" dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
