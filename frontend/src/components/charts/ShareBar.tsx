"use client";

import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { num, pkr } from "@/lib/format";
import ChartTooltip from "./ChartTooltip";

export interface ShareRow {
  label: string;
  value: number;
  /** optional secondary figure shown in the list (e.g. "121 inv", "75 items") */
  note?: string;
}

const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--series-5)", "var(--series-6)"];
const MAX_SEGMENTS = 5;

/**
 * Part-to-whole as a single 100% stacked horizontal bar plus a legend list.
 * Categorical hues are assigned in fixed order; anything past the 5th folds into "Other".
 */
export default function ShareBar({ rows, total }: { rows: ShareRow[]; total?: number }) {
  const sum = total ?? rows.reduce((s, r) => s + Math.max(0, r.value), 0);
  const sorted = [...rows].filter((r) => r.value > 0).sort((a, b) => b.value - a.value);
  const head = sorted.slice(0, MAX_SEGMENTS);
  const tail = sorted.slice(MAX_SEGMENTS);
  const segments: ShareRow[] = tail.length ? [...head, { label: "Other", value: tail.reduce((s, r) => s + r.value, 0), note: `${tail.length} more` }] : head;
  const datum: Record<string, number | string> = { name: "share" };
  segments.forEach((s, i) => (datum[`s${i}`] = s.value));

  return (
    <div className="flex flex-col gap-3">
      <ResponsiveContainer width="100%" height={44}>
        <BarChart data={[datum]} layout="vertical" margin={{ top: 4, right: 0, left: 0, bottom: 4 }} barCategoryGap={0}>
          <XAxis type="number" hide domain={[0, sum || 1]} />
          <YAxis type="category" dataKey="name" hide />
          <Tooltip cursor={false} content={<ChartTooltip format={(v) => `${pkr(v)} · ${sum ? ((v / sum) * 100).toFixed(1) : 0}%`} labelFormat={() => ""} />} />
          {segments.map((s, i) => (
            <Bar
              key={s.label}
              dataKey={`s${i}`}
              name={s.label}
              stackId="share"
              fill={SERIES[i]}
              stroke="var(--surface)"
              strokeWidth={2}
              isAnimationActive={false}
              radius={i === 0 ? [6, 0, 0, 6] : i === segments.length - 1 ? [0, 6, 6, 0] : 0}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <ul className="flex flex-col gap-1.5 text-xs">
        {segments.map((s, i) => (
          <li key={s.label} className="flex items-center justify-between gap-3">
            <span className="flex min-w-0 items-center gap-2 text-ink-2">
              <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: SERIES[i] }} />
              <span className="truncate text-ink">{s.label}</span>
              {s.note && <span className="shrink-0 text-ink-3">· {s.note}</span>}
            </span>
            <span className="tnum shrink-0 text-ink-2">
              <span className="font-medium text-ink">{pkr(s.value)}</span> · {sum ? num((s.value / sum) * 100, 1) : 0}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
