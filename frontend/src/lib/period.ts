import { useSearchParams } from "react-router";
import { useSummary } from "../api/queries";

export const ALL_PERIODS = "all";

/**
 * The period a dashboard view shows, kept in the URL (?period=202608 or ?period=all).
 * Without one, the latest loaded month is shown when `defaultLatest` is set.
 */
export function usePeriod({ defaultLatest }: { defaultLatest: boolean }) {
  const [params, setParams] = useSearchParams();
  const all = useSummary();
  const periods = all.data?.periods ?? [];
  const requested = params.get("period");
  const latest = periods.length ? periods[periods.length - 1] : undefined;
  const selected =
    requested === ALL_PERIODS
      ? undefined
      : requested && /^\d{6}$/.test(requested)
        ? requested
        : defaultLatest
          ? latest
          : undefined;

  const setPeriod = (period: string | undefined) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set("period", period ?? ALL_PERIODS);
        return next;
      },
      { replace: true },
    );
  };

  return { period: selected, periods, setPeriod, ready: !all.isPending, error: all.error };
}
