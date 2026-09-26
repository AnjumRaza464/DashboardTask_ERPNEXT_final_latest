"use client";

import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { compact, fmtDate, fmtPeriod, pkr } from "@/lib/format";
import type { PnlTrend } from "@/lib/types";
import ChartTooltip from "./ChartTooltip";

export default function PnlTrendChart({ data, height = 260 }: { data: PnlTrend; height?: number }) {
  const points = data.points.map((p) => ({ ...p, label: fmtPeriod(p.period, data.granularity) }));
  const tickEvery = Math.max(1, Math.ceil(points.length / 8));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 8, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeWidth={1} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} interval={tickEvery - 1} dy={6} />
        <YAxis tickFormatter={(v: number) => compact(v)} tickLine={false} axisLine={false} width={52} />
        <ReferenceLine y={0} stroke="var(--axis)" />
        <Tooltip
          cursor={{ strokeWidth: 1 }}
          content={<ChartTooltip labelFormat={(_, e) => (data.granularity === "day" ? fmtDate(String(e?.payload?.period)) : String(e?.payload?.label))} format={(v) => pkr(v)} />}
        />
        <Legend iconType="plainline" iconSize={14} wrapperStyle={{ paddingTop: 8 }} />
        <Line isAnimationActive={false} type="monotone" dataKey="income" name="Income" stroke="var(--series-1)" strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }} />
        <Line isAnimationActive={false} type="monotone" dataKey="expense" name="Expenses" stroke="var(--series-2)" strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }} />
        <Line isAnimationActive={false} type="monotone" dataKey="net" name="Net" stroke="var(--series-3)" strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
