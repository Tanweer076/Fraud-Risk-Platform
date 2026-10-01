import type { ReactNode } from "react";
import { cx } from "../lib/cx";

/** One headline number: label, value, and a line of context. */
export function StatTile({
  label,
  value,
  context,
  className,
}: {
  label: string;
  value: ReactNode;
  context?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("rounded-lg border border-line bg-surface px-4 py-3", className)}>
      <p className="text-xs text-ink-2">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
      {context && <p className="mt-0.5 text-xs text-ink-2">{context}</p>}
    </div>
  );
}
