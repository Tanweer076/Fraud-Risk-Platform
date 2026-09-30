import { Link } from "react-router";
import { useRiskDistribution, useSummary, useTransactions } from "../api/queries";
import { BandBadge } from "../components/BandBadge";
import { BreakRateTrend } from "../components/BreakRateTrend";
import { ChartCard } from "../components/charts/ChartCard";
import { HBarChart } from "../components/charts/HBarChart";
import { PeriodSelect } from "../components/PeriodSelect";
import { StatTile } from "../components/StatTile";
import { BreakChips } from "../components/TransactionBits";
import { Card, Empty, ErrorState, Loading, PageHeader } from "../components/ui";
import { BAND_COLOR, BAND_LABEL, BANDS } from "../lib/bands";
import { cx, table as t } from "../lib/cx";
import {
  formatCompact,
  formatDate,
  formatMoney,
  formatNumber,
  formatPercent,
  formatPeriod,
  formatUsd,
} from "../lib/format";
import { usePeriod } from "../lib/period";
import { DEFAULT_SORT, transactionsLink } from "../lib/transactionFilters";

function Kpis({ period }: { period: string | undefined }) {
  const summary = useSummary(period);
  if (summary.isPending) return <Loading label="Loading figures" />;
  if (summary.isError)
    return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />;
  const s = summary.data;
  return (
    <div
      className={cx(
        "grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6",
        summary.isPlaceholderData && "opacity-60",
      )}
    >
      <StatTile
        label="Transactions"
        value={formatCompact(s.transactions)}
        context={`${formatCompact(s.scored)} scored`}
      />
      <StatTile
        label="With breaks"
        value={formatCompact(s.suspicious)}
        context={`${formatPercent(s.suspicious_rate)} of transactions`}
      />
      <StatTile
        label="High or critical"
        value={formatCompact(s.high_or_critical)}
        context={
          s.avg_risk_score == null ? undefined : `Average score ${s.avg_risk_score.toFixed(1)}`
        }
      />
      <StatTile
        label="Exposure at risk"
        value={formatUsd(s.exposure_usd_at_risk)}
        context="USD in high and critical breaks"
      />
      <StatTile
        label="Review queue"
        value={formatCompact(s.review_queue)}
        context="Flagged, not yet reviewed"
      />
      <StatTile
        label="Awaiting approval"
        value={formatCompact(s.pending_approval)}
        context={`${formatNumber(s.confirmed)} confirmed · ${formatNumber(s.false_positive)} false positive`}
      />
    </div>
  );
}

function BandsCard({ period }: { period: string | undefined }) {
  const distribution = useRiskDistribution(period);
  const bands = distribution.data?.bands ?? [];
  const byBand = new Map(bands.map((b) => [b.band, b]));
  const rows = [...BANDS].reverse().map((band) => ({
    band,
    count: byBand.get(band)?.count ?? 0,
    share: byBand.get(band)?.share ?? 0,
  }));
  return (
    <ChartCard
      title="Risk bands"
      subtitle="Transactions by band of their latest score"
      refreshing={distribution.isPlaceholderData}
      table={{
        columns: [
          { key: "band", label: "Band" },
          { key: "count", label: "Transactions", numeric: true },
          { key: "share", label: "Share", numeric: true },
        ],
        rows: rows.map((r) => ({
          band: BAND_LABEL[r.band],
          count: formatNumber(r.count),
          share: formatPercent(r.share),
        })),
      }}
    >
      {distribution.isPending ? (
        <Loading />
      ) : distribution.isError ? (
        <ErrorState error={distribution.error} />
      ) : (
        <HBarChart
          label="Transactions by risk band"
          labelWidth="6rem"
          format={formatNumber}
          bars={rows.map((r) => ({
            key: r.band,
            label: BAND_LABEL[r.band],
            value: r.count,
            color: BAND_COLOR[r.band],
            href: transactionsLink({ period, band: r.band }),
            details: [{ label: "Share", value: formatPercent(r.share) }],
          }))}
        />
      )}
    </ChartCard>
  );
}

function TopTransactions({ period }: { period: string | undefined }) {
  const query = useTransactions({ period, suspicious: true, reviewed: false }, DEFAULT_SORT, 1, 10);
  return (
    <Card
      title="Highest priority, not yet reviewed"
      subtitle="Priority weights the risk score by the money at stake"
      actions={
        <Link
          to={transactionsLink({ period, suspicious: true, reviewed: false })}
          className="text-xs font-medium text-accent-text hover:underline"
        >
          View all
        </Link>
      }
      bodyClassName="p-0"
    >
      {query.isPending ? (
        <div className="px-4">
          <Loading />
        </div>
      ) : query.isError ? (
        <div className="p-4">
          <ErrorState error={query.error} />
        </div>
      ) : query.data.items.length === 0 ? (
        <Empty>Nothing waiting: every flagged transaction has been reviewed.</Empty>
      ) : (
        <div className={cx(t.wrap, query.isPlaceholderData && "opacity-60")}>
          <table className={t.table}>
            <thead>
              <tr>
                <th scope="col" className={t.th}>
                  Transaction
                </th>
                <th scope="col" className={t.th}>
                  Date
                </th>
                <th scope="col" className={cx(t.th, t.num)}>
                  Amount
                </th>
                <th scope="col" className={t.th}>
                  Breaks
                </th>
                <th scope="col" className={t.th}>
                  Risk
                </th>
                <th scope="col" className={cx(t.th, t.num)}>
                  Priority
                </th>
                <th scope="col" className={cx(t.th, t.num)}>
                  Exposure
                </th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((tx) => (
                <tr key={tx.transaction_id} className={t.row}>
                  <td className={t.td}>
                    <Link
                      to={`/transactions/${encodeURIComponent(tx.transaction_id)}`}
                      className="font-mono text-xs font-medium text-accent-text hover:underline"
                    >
                      {tx.transaction_id}
                    </Link>
                  </td>
                  <td className={cx(t.td, "whitespace-nowrap")}>
                    {formatDate(tx.transaction_date)}
                  </td>
                  <td className={cx(t.td, t.num, "whitespace-nowrap")}>
                    {formatMoney(tx.amount, tx.currency)}
                  </td>
                  <td className={t.td}>
                    <BreakChips breaks={tx.break_types} limit={2} />
                  </td>
                  <td className={t.td}>
                    <BandBadge band={tx.risk_band} score={tx.risk_score} />
                  </td>
                  <td className={cx(t.td, t.num)}>{tx.priority}</td>
                  <td className={cx(t.td, t.num, "whitespace-nowrap")}>
                    {formatUsd(tx.exposure_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function DashboardPage() {
  const { period, periods, setPeriod, ready, error } = usePeriod({ defaultLatest: true });
  return (
    <>
      <PageHeader
        title="Dashboard"
        description={
          period
            ? `Cross-system breaks and risk for ${formatPeriod(period)}.`
            : "Cross-system breaks and risk across all loaded months."
        }
        actions={<PeriodSelect period={period} periods={periods} onChange={setPeriod} />}
      />
      {error ? (
        <ErrorState error={error} />
      ) : !ready ? (
        <Loading />
      ) : periods.length === 0 ? (
        <Card>
          <Empty>
            No data loaded yet. Upload a month on the{" "}
            <Link to="/ingestion" className="text-accent-text underline">
              Data ingestion
            </Link>{" "}
            page.
          </Empty>
        </Card>
      ) : (
        <div className="space-y-5">
          <Kpis period={period} />
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <BandsCard period={period} />
            <BreakRateTrend period={period} />
          </div>
          <TopTransactions period={period} />
        </div>
      )}
    </>
  );
}
