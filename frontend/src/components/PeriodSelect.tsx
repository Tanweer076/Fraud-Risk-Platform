import { formatPeriod } from "../lib/format";
import { ALL_PERIODS } from "../lib/period";
import { Select } from "./ui";

export function PeriodSelect({
  period,
  periods,
  onChange,
}: {
  period: string | undefined;
  periods: string[];
  onChange: (period: string | undefined) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-xs font-medium text-ink-2">
      Period
      <Select
        className="w-auto min-w-36"
        value={period ?? ALL_PERIODS}
        onChange={(event) =>
          onChange(event.target.value === ALL_PERIODS ? undefined : event.target.value)
        }
      >
        <option value={ALL_PERIODS}>All periods</option>
        {[...periods].reverse().map((p) => (
          <option key={p} value={p}>
            {formatPeriod(p)}
          </option>
        ))}
      </Select>
    </label>
  );
}
