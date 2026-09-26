"use client";

import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { compact, pkr } from "@/lib/format";
import ChartTooltip, { type TooltipEntry } from "./ChartTooltip";

const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--series-5)", "var(--series-6)"];

interface Props {
  /** rows carry `label` plus one numeric field per group key */
  data: Record<string, unknown>[];
  /** group keys in fixed (colour) order; at most 6 */
  groups: string[];
  height?: number;
  labelFormat?: (label: string | number, entry?: TooltipEntry) => string;
}

/** Stacked columns per period, one colour per group in fixed order. Negative values stack below zero. */
export default function StackedColumns({ data, groups, height = 260, labelFormat }: Props) {
  const tickEvery = Math.max(1, Math.ceil(data.length / 8));
  const hasNegative = data.some((row) => groups.some((g) => Number(row[g] ?? 0) < 0));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="25%" stackOffset="sign">
        <CartesianGrid vertical={false} strokeWidth={1} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} dy={6} interval={tickEvery - 1} />
        <YAxis tickFormatter={(v: number) => compact(v)} tickLine={false} axisLine={false} width={52} />
        {hasNegative && <ReferenceLine y={0} stroke="var(--axis)" />}
        <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<ChartTooltip labelFormat={labelFormat} format={(v) => pkr(v)} />} />
        <Legend iconType="square" iconSize={10} wrapperStyle={{ paddingTop: 8 }} />
        {groups.slice(0, SERIES.length).map((g, i) => (
          <Bar key={g} dataKey={g} name={g} stackId="stack" fill={SERIES[i]} stroke="var(--surface)" strokeWidth={1} maxBarSize={56} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
