import type { Factor } from "../api/client";
import { Empty } from "./ui";

const RAISES = "var(--status-critical)";
const LOWERS = "var(--series-1)";

/**
 * The model's top reasons for one score. Bars diverge from a centre line: right raises the risk,
 * left lowers it; length is the contribution in log-odds, labelled with its sign.
 */
export function FactorBars({ factors }: { factors: Factor[] }) {
  if (factors.length === 0) {
    return <Empty>No model explanation for this score.</Empty>;
  }
  const largest = Math.max(...factors.map((f) => Math.abs(f.contribution)), 1e-9);
  return (
    <div>
      <ul className="space-y-2.5" aria-label="What drove the model score">
        {factors.map((factor, index) => {
          const share = Math.abs(factor.contribution) / largest;
          const raises = factor.contribution >= 0;
          return (
            <li key={index}>
              <p className="text-sm text-ink">{factor.reason}</p>
              <div className="mt-1 grid grid-cols-[1fr_1fr_auto] items-center gap-0">
                <span className="flex h-3 justify-end">
                  {!raises && (
                    <span
                      className="h-3 rounded-l"
                      style={{ width: `${share * 100}%`, background: LOWERS }}
                    />
                  )}
                </span>
                <span className="flex h-3 border-l border-[color:var(--axis)]">
                  {raises && (
                    <span
                      className="h-3 rounded-r"
                      style={{ width: `${share * 100}%`, background: RAISES }}
                    />
                  )}
                </span>
                <span className="w-16 pl-2 text-right text-xs text-ink-2 tabular-nums">
                  {raises ? "+" : "−"}
                  {Math.abs(factor.contribution).toFixed(2)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: RAISES }} />
          Raises risk
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: LOWERS }} />
          Lowers risk
        </span>
        <span>Contribution in log-odds.</span>
      </p>
    </div>
  );
}
