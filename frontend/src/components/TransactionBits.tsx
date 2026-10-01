import type { TransactionSummary } from "../api/client";
import { breakLabel } from "../lib/format";
import { Icon } from "./Icon";
import { Chip } from "./ui";

/** Which systems hold the record: present systems plain, missing ones struck through. */
export function SystemsPresence({
  tx,
}: {
  tx: Pick<TransactionSummary, "in_gl" | "in_ma" | "in_fa">;
}) {
  const systems = [
    ["GL", tx.in_gl],
    ["MA", tx.in_ma],
    ["FA", tx.in_fa],
  ] as const;
  return (
    <span className="inline-flex gap-1 text-xs">
      {systems.map(([name, present]) => (
        <span
          key={name}
          className={
            present
              ? "rounded border border-line px-1 text-ink-2"
              : "rounded border border-dashed border-critical/60 px-1 text-danger line-through"
          }
          title={present ? `In ${name}` : `Missing in ${name}`}
        >
          {name}
          <span className="sr-only">{present ? " present" : " missing"}</span>
        </span>
      ))}
    </span>
  );
}

export function BreakChips({ breaks, limit = 3 }: { breaks: string[]; limit?: number }) {
  if (breaks.length === 0) return <span className="text-xs text-ink-3">None</span>;
  const shown = breaks.slice(0, limit);
  return (
    <span className="flex flex-wrap gap-1">
      {shown.map((code) => (
        <Chip key={code}>{breakLabel(code)}</Chip>
      ))}
      {breaks.length > limit && <Chip>+{breaks.length - limit}</Chip>}
    </span>
  );
}

const OUTCOME_LABEL: Record<string, string> = {
  confirmed: "Confirmed",
  false_positive: "False positive",
};

export function ReviewOutcome({ outcome }: { outcome: string | null | undefined }) {
  if (!outcome) return <span className="text-xs whitespace-nowrap text-ink-3">Not reviewed</span>;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-ink">
      <Icon name={outcome === "confirmed" ? "alert" : "check"} size={14} className="text-ink-2" />
      {OUTCOME_LABEL[outcome] ?? outcome}
    </span>
  );
}
