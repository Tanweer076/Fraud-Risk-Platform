import { useTrends } from "../api/queries";
import { formatNumber, formatPercent, formatPercentTick, formatPeriod } from "../lib/format";
import { ChartCard } from "./charts/ChartCard";
import { TrendChart } from "./charts/Charts";
import { Empty, ErrorState, Loading } from "./ui";

/** Break rate over time: by day within a selected month, or by month across all of them. */
export function BreakRateTrend({ period }: { period: string | undefined }) {
  const granularity = period ? "day" : "month";
  const trends = useTrends(granularity, period);
  // Rows dated outside their month (a date break) would add spikes at the edges of a daily chart.
  const month = period ? `${period.slice(0, 4)}-${period.slice(4)}` : "";
  const rows = (trends.data ?? []).filter((p) => !period || p.bucket.startsWith(month));
  const outside = (trends.data ?? [])
    .filter((p) => period && !p.bucket.startsWith(month))
    .reduce((sum, p) => sum + p.transactions, 0);
  const points = rows.map((p) => ({
    x: p.bucket,
    y: p.suspicious_rate,
    details: [
      { label: "Transactions", value: formatNumber(p.transactions) },
      { label: "With breaks", value: formatNumber(p.suspicious) },
    ],
  }));
  return (
    <ChartCard
      title={period ? "Break rate by day" : "Break rate by month"}
      subtitle={
        outside > 0
          ? `Share of transactions with at least one break. ${formatNumber(outside)} dated outside the month are not shown.`
          : "Share of transactions with at least one break"
      }
      refreshing={trends.isPlaceholderData}
      table={{
        columns: [
          { key: "bucket", label: period ? "Day" : "Month" },
          { key: "transactions", label: "Transactions", numeric: true },
          { key: "suspicious", label: "With breaks", numeric: true },
          { key: "rate", label: "Rate", numeric: true },
        ],
        rows: rows.map((p) => ({
          bucket: period ? p.bucket : formatPeriod(p.bucket),
          transactions: formatNumber(p.transactions),
          suspicious: formatNumber(p.suspicious),
          rate: formatPercent(p.suspicious_rate),
        })),
      }}
    >
      {trends.isPending ? (
        <Loading />
      ) : trends.isError ? (
        <ErrorState error={trends.error} />
      ) : points.length === 0 ? (
        <Empty>No transactions in this period.</Empty>
      ) : (
        <TrendChart
          points={points}
          seriesLabel="Break rate"
          yFormat={(v) => formatPercent(v)}
          yTickFormat={formatPercentTick}
          xFormat={(x) => (period ? x.slice(5) : formatPeriod(x))}
        />
      )}
    </ChartCard>
  );
}
