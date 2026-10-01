/**
 * Recharts wrappers that apply the chart rules once: thin marks (bars <= 24px with a 4px rounded
 * end, 2px lines, 8px dots with a surface ring), hairline grid, text on ink tokens, a tooltip on
 * every mark, and no animation (numbers should not wobble on refetch).
 */
import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCompact, formatTick } from "../../lib/format";
import { TooltipBox } from "./HBarChart";

export interface Detail {
  label: string;
  value: string;
}

interface Hover<T> {
  active?: boolean;
  payload?: readonly { payload?: T }[];
}

function hovered<T>(props: Hover<T>): T | undefined {
  return props.active ? props.payload?.[0]?.payload : undefined;
}

const AXIS_TICK = { fill: "var(--ink-3)", fontSize: 12 };

// Columns ----------------------------------------------------------------------------------

export interface Column {
  key: string;
  label: string;
  value: number;
  color?: string;
  details?: Detail[];
}

export function ColumnChart({
  columns,
  format = formatCompact,
  height = 240,
  xLabel,
}: {
  columns: Column[];
  format?: (value: number) => string;
  height?: number;
  xLabel?: string;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={columns} margin={{ top: 20, right: 4, bottom: xLabel ? 16 : 0, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="label"
            tick={AXIS_TICK}
            tickLine={false}
            interval={0}
            label={xLabel ? { value: xLabel, position: "insideBottom", offset: -10 } : undefined}
          />
          <YAxis
            tick={AXIS_TICK}
            tickFormatter={formatTick}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip
            cursor={{ fill: "var(--subtle)" }}
            content={(props) => {
              const column = hovered<Column>(props as Hover<Column>);
              if (!column) return null;
              return (
                <TooltipBox
                  title={column.label}
                  rows={[
                    { label: "Count", value: format(column.value) },
                    ...(column.details ?? []),
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false}>
            {columns.map((column) => (
              <Cell key={column.key} fill={column.color ?? "var(--series-1)"} />
            ))}
            <LabelList
              dataKey="value"
              position="top"
              fill="var(--ink-2)"
              fontSize={11}
              formatter={(value: unknown) =>
                typeof value === "number" && value > 0 ? format(value) : ""
              }
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Trend over time ----------------------------------------------------------------------------

export interface TrendPoint {
  x: string;
  y: number | null;
  details?: Detail[];
}

export function TrendChart({
  points,
  yFormat,
  yTickFormat = yFormat,
  xFormat = (x) => x,
  yDomain,
  seriesLabel,
  height = 240,
}: {
  points: TrendPoint[];
  yFormat: (value: number) => string;
  /** Axis ticks, when they need a plainer format than tooltips and labels. */
  yTickFormat?: (value: number) => string;
  xFormat?: (x: string) => string;
  yDomain?: [number, number | "auto"];
  seriesLabel: string;
  height?: number;
}) {
  const lastIndex = points.length - 1;
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 16, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="x"
            tick={AXIS_TICK}
            tickLine={false}
            minTickGap={28}
            tickFormatter={xFormat}
          />
          <YAxis
            tick={AXIS_TICK}
            tickFormatter={(v: number) => yTickFormat(v)}
            tickLine={false}
            axisLine={false}
            width={48}
            domain={yDomain ?? [0, "auto"]}
          />
          <Tooltip
            cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
            content={(props) => {
              const point = hovered<TrendPoint>(props as Hover<TrendPoint>);
              if (!point) return null;
              return (
                <TooltipBox
                  title={xFormat(point.x)}
                  rows={[
                    {
                      label: seriesLabel,
                      value: point.y == null ? "—" : yFormat(point.y),
                      color: "var(--series-1)",
                    },
                    ...(point.details ?? []),
                  ]}
                />
              );
            }}
          />
          <Area
            type="linear"
            dataKey="y"
            stroke="var(--series-1)"
            strokeWidth={2}
            fill="var(--series-1-wash)"
            fillOpacity={1}
            dot={false}
            activeDot={{ r: 4, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }}
            isAnimationActive={false}
          >
            <LabelList
              dataKey="y"
              content={(props: {
                x?: number | string;
                y?: number | string;
                value?: unknown;
                index?: number;
              }) =>
                props.index === lastIndex && typeof props.value === "number" ? (
                  <text
                    x={Number(props.x) + 8}
                    y={Number(props.y)}
                    dy={4}
                    fill="var(--ink)"
                    fontSize={12}
                    fontWeight={600}
                  >
                    {yFormat(props.value)}
                  </text>
                ) : null
              }
            />
          </Area>
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Curves on a 0-1 x 0-1 plane (precision-recall, ROC, calibration) -----------------------------

export interface CurvePoint {
  x: number;
  y: number;
  details?: Detail[];
}

const UNIT_TICKS = [0, 0.25, 0.5, 0.75, 1];
const pct = (v: number) => `${Math.round(v * 100)}%`;

export function CurveChart({
  points,
  xLabel,
  yLabel,
  diagonal = false,
  step = false,
  height = 260,
  note,
}: {
  points: CurvePoint[];
  xLabel: string;
  yLabel: string;
  diagonal?: boolean;
  step?: boolean;
  height?: number;
  note?: ReactNode;
}) {
  const sorted = [...points].sort((a, b) => a.x - b.x || a.y - b.y);
  return (
    <div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={sorted} margin={{ top: 8, right: 16, bottom: 20, left: 4 }}>
            <CartesianGrid />
            <XAxis
              type="number"
              dataKey="x"
              domain={[0, 1]}
              ticks={UNIT_TICKS}
              tickFormatter={pct}
              tick={AXIS_TICK}
              tickLine={false}
              label={{ value: xLabel, position: "insideBottom", offset: -12 }}
            />
            <YAxis
              type="number"
              domain={[0, 1]}
              ticks={UNIT_TICKS}
              tickFormatter={pct}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={60}
              // Centred in the space left of the tick labels.
              label={{
                value: yLabel,
                angle: -90,
                position: "insideLeft",
                offset: 6,
                style: { textAnchor: "middle" },
              }}
            />
            {diagonal && (
              <ReferenceLine
                segment={[
                  { x: 0, y: 0 },
                  { x: 1, y: 1 },
                ]}
                stroke="var(--axis)"
                strokeWidth={1}
                ifOverflow="extendDomain"
              />
            )}
            <Tooltip
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
              content={(props) => {
                const point = hovered<CurvePoint>(props as Hover<CurvePoint>);
                if (!point) return null;
                return (
                  <TooltipBox
                    title={`${xLabel} ${pct(point.x)}`}
                    rows={[
                      { label: yLabel, value: pct(point.y), color: "var(--series-1)" },
                      ...(point.details ?? []),
                    ]}
                  />
                );
              }}
            />
            <Line
              type={step ? "stepAfter" : "linear"}
              dataKey="y"
              stroke="var(--series-1)"
              strokeWidth={2}
              dot={{ r: 4, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }}
              activeDot={{
                r: 5,
                fill: "var(--series-1)",
                stroke: "var(--surface)",
                strokeWidth: 2,
              }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {note && <p className="mt-1 text-xs text-ink-2">{note}</p>}
    </div>
  );
}
