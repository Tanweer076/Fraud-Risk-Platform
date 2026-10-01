import { type ReactNode, useState } from "react";
import { Link } from "react-router";

export interface HBar {
  key: string;
  label: string;
  value: number;
  /** Defaults to series 1. Pass a status colour only when the bar means a state. */
  color?: string;
  /** Extra lines for the hover and focus tooltip. */
  details?: { label: string; value: string }[];
  href?: string;
}

/**
 * Horizontal bars in plain HTML: labels on the left, bars growing from one baseline with the
 * value at the tip. Each row is focusable and shows its details on hover or focus.
 */
export function HBarChart({
  bars,
  format,
  max,
  labelWidth = "11rem",
  label,
}: {
  bars: HBar[];
  format: (value: number) => string;
  max?: number;
  labelWidth?: string;
  label: string;
}) {
  const [active, setActive] = useState<string | null>(null);
  const top = max ?? Math.max(0, ...bars.map((bar) => bar.value));

  return (
    <ul aria-label={label} className="space-y-1">
      {bars.map((bar) => {
        const share = top > 0 ? Math.max(0, bar.value) / top : 0;
        const text = format(bar.value);
        return (
          <li
            key={bar.key}
            tabIndex={0}
            aria-label={`${bar.label}: ${text}`}
            onMouseEnter={() => setActive(bar.key)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(bar.key)}
            onBlur={() => setActive(null)}
            className="relative grid items-center gap-3 rounded outline-offset-1 hover:bg-subtle focus-visible:bg-subtle"
            style={{ gridTemplateColumns: `minmax(0, ${labelWidth}) minmax(0, 1fr)` }}
          >
            <span className="truncate py-0.5 pl-1 text-xs text-ink-2" title={bar.label}>
              {bar.href ? (
                <Link to={bar.href} className="hover:text-ink hover:underline" tabIndex={-1}>
                  {bar.label}
                </Link>
              ) : (
                bar.label
              )}
            </span>
            <span className="flex h-6 items-center border-l border-[color:var(--axis)]">
              <span
                className="h-4 rounded-r"
                style={{
                  width: `calc(${share} * (100% - 5.5rem))`,
                  minWidth: bar.value > 0 ? 2 : 0,
                  background: bar.color ?? "var(--series-1)",
                }}
              />
              <span className="ml-2 text-xs whitespace-nowrap text-ink tabular-nums">{text}</span>
            </span>
            {active === bar.key && (
              <span
                role="tooltip"
                className="pointer-events-none absolute right-2 bottom-full z-10 mb-1 min-w-40 rounded-md border border-line bg-surface px-2.5 py-2 text-xs shadow-lg"
              >
                <span className="block font-semibold text-ink">{text}</span>
                <span className="block text-ink-2">{bar.label}</span>
                {bar.details?.map((detail) => (
                  <span key={detail.label} className="mt-0.5 flex justify-between gap-3 text-ink-2">
                    <span>{detail.label}</span>
                    <span className="font-medium text-ink tabular-nums">{detail.value}</span>
                  </span>
                ))}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Label/value rows for a tooltip. */
export function TooltipBox({
  title,
  rows,
}: {
  title: ReactNode;
  rows: { label: ReactNode; value: ReactNode; color?: string }[];
}) {
  return (
    <div className="min-w-36 rounded-md border border-line bg-surface px-2.5 py-2 text-xs shadow-lg">
      <p className="mb-1 text-ink-2">{title}</p>
      {rows.map((row, index) => (
        <p key={index} className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-ink-2">
            {row.color && (
              <span className="inline-block h-0.5 w-3 rounded" style={{ background: row.color }} />
            )}
            {row.label}
          </span>
          <span className="font-semibold text-ink tabular-nums">{row.value}</span>
        </p>
      ))}
    </div>
  );
}
