"use client";

import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { compact, pkr } from "@/lib/format";
import type { AgeingBucket } from "@/lib/types";
import ChartTooltip from "./ChartTooltip";

const ORDINAL = ["var(--ord-1)", "var(--ord-2)", "var(--ord-3)", "var(--ord-4)", "var(--ord-5)"];

/** Ageing buckets (receivables or payables): ordered buckets → ordinal blue ramp (validated). */
export default function AgeingChart({ buckets, seriesName = "Outstanding", height = 260 }: { buckets: AgeingBucket[]; seriesName?: string; height?: number }) {
  const rows = buckets.map((b) => ({ label: `${b.bucket} days`, value: b.amount }));
  const hasNegative = rows.some((r) => r.value < 0);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="30%">
        <CartesianGrid vertical={false} strokeWidth={1} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} dy={6} />
        <YAxis tickFormatter={(v: number) => compact(v)} tickLine={false} axisLine={false} width={48} />
        {hasNegative && <ReferenceLine y={0} stroke="var(--axis)" />}
        <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<ChartTooltip noSwatch format={(v) => pkr(v)} />} />
        <Bar dataKey="value" name={seriesName} radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
          {rows.map((_, i) => (
            <Cell key={i} fill={ORDINAL[i]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
