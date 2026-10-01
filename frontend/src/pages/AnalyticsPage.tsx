import { useState } from "react";
import { Link } from "react-router";
import {
  type BreakdownBy,
  useBreakdown,
  useRiskDistribution,
  useTopAccounts,
} from "../api/queries";
import { BreakRateTrend } from "../components/BreakRateTrend";
import { ChartCard } from "../components/charts/ChartCard";
import { ColumnChart } from "../components/charts/Charts";
import { HBarChart } from "../components/charts/HBarChart";
import { PeriodSelect } from "../components/PeriodSelect";
import { Card, Empty, ErrorState, Loading, PageHeader, Segmented } from "../components/ui";
import { BAND_COLOR, BAND_LABEL, BANDS, bandFor } from "../lib/bands";
import { cx, table as t } from "../lib/cx";
import {
  breakLabel,
  DASH,
  formatDate,
  formatNumber,
  formatPercent,
  formatUsd,
} from "../lib/format";
import { usePeriod } from "../lib/period";
import { transactionsLink } from "../lib/transactionFilters";

function ScoreDistribution({ period }: { period: string | undefined }) {
  const query = useRiskDistribution(period);
  const bins = query.data?.bins ?? [];
  return (
    <ChartCard
      title="Risk score distribution"
      subtitle="Transactions per 10-point score bin, coloured by band"
      refreshing={query.isPlaceholderData}
      table={{
        columns: [
          { key: "bin", label: "Score" },
          { key: "band", label: "Band" },
          { key: "count", label: "Transactions", numeric: true },
        ],
        rows: bins.map((b) => ({
          bin: `${b.score_from}–${b.score_to}`,
          band: BAND_LABEL[bandFor(b.score_from)],
          count: formatNumber(b.count),
        })),
      }}
    >
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState error={query.error} />
      ) : (
        <>
          <ColumnChart
            xLabel="Risk score"
            columns={bins.map((b) => ({
              key: String(b.score_from),
              label: `${b.score_from}`,
              value: b.count,
              color: BAND_COLOR[bandFor(b.score_from)],
              details: [
                { label: "Scores", value: `${b.score_from}–${b.score_to}` },
                { label: "Band", value: BAND_LABEL[bandFor(b.score_from)] },
              ],
            }))}
          />
          <ul
            className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2"
            aria-label="Legend"
          >
            {BANDS.map((band) => (
              <li key={band} className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ background: BAND_COLOR[band] }}
                />
                {BAND_LABEL[band]}
              </li>
            ))}
          </ul>
        </>
      )}
    </ChartCard>
  );
}

function BreakTypes({ period }: { period: string | undefined }) {
  const query = useBreakdown("break_type", period);
  const rows = [...(query.data ?? [])].sort((a, b) => b.transactions - a.transactions);
  return (
    <ChartCard
      title="Breaks by type"
      subtitle="Transactions with each break (one transaction can have several)"
      refreshing={query.isPlaceholderData}
      table={{
        columns: [
          { key: "type", label: "Break type" },
          { key: "count", label: "Transactions", numeric: true },
          { key: "exposure", label: "Exposure (USD)", numeric: true },
          { key: "score", label: "Average score", numeric: true },
        ],
        rows: rows.map((r) => ({
          type: breakLabel(r.key ?? ""),
          count: formatNumber(r.transactions),
          exposure: formatUsd(r.exposure_usd),
          score: r.avg_risk_score?.toFixed(1) ?? DASH,
        })),
      }}
    >
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState error={query.error} />
      ) : rows.length === 0 ? (
        <Empty>No breaks in this period.</Empty>
      ) : (
        <HBarChart
          label="Transactions by break type"
          format={formatNumber}
          bars={rows.map((r) => ({
            key: r.key ?? "none",
            label: breakLabel(r.key ?? ""),
            value: r.transactions,
            href: transactionsLink({ period, break_type: r.key ?? undefined }),
            details: [
              { label: "Exposure", value: formatUsd(r.exposure_usd) },
              { label: "Average score", value: r.avg_risk_score?.toFixed(1) ?? DASH },
            ],
          }))}
        />
      )}
    </ChartCard>
  );
}

const DIMENSIONS: { value: BreakdownBy; label: string }[] = [
  { value: "currency", label: "Currency" },
  { value: "country", label: "Country" },
  { value: "description", label: "Description" },
];

function Segments({ period }: { period: string | undefined }) {
  const [by, setBy] = useState<BreakdownBy>("currency");
  const query = useBreakdown(by, period);
  const rows = [...(query.data ?? [])].sort((a, b) => b.suspicious_rate - a.suspicious_rate);
  const dimension = DIMENSIONS.find((d) => d.value === by)?.label ?? by;
  return (
    <ChartCard
      title={`Break rate by ${dimension.toLowerCase()}`}
      subtitle="Similar rates across segments mean the attribute on its own doesn't predict breaks"
      refreshing={query.isPlaceholderData}
      actions={<Segmented label="Segment by" value={by} options={DIMENSIONS} onChange={setBy} />}
      table={{
        columns: [
          { key: "key", label: dimension },
          { key: "transactions", label: "Transactions", numeric: true },
          { key: "suspicious", label: "With breaks", numeric: true },
          { key: "rate", label: "Rate", numeric: true },
          { key: "exposure", label: "Exposure (USD)", numeric: true },
        ],
        rows: rows.map((r) => ({
          key: r.key ?? "(blank)",
          transactions: formatNumber(r.transactions),
          suspicious: formatNumber(r.suspicious),
          rate: formatPercent(r.suspicious_rate),
          exposure: formatUsd(r.exposure_usd),
        })),
      }}
    >
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState error={query.error} />
      ) : rows.length === 0 ? (
        <Empty>No transactions in this period.</Empty>
      ) : (
        <HBarChart
          label={`Break rate by ${dimension.toLowerCase()}`}
          format={formatPercent}
          labelWidth="9rem"
          bars={rows.map((r) => ({
            key: r.key ?? "(blank)",
            label: r.key ?? "(blank)",
            value: r.suspicious_rate,
            details: [
              { label: "Transactions", value: formatNumber(r.transactions) },
              { label: "With breaks", value: formatNumber(r.suspicious) },
              { label: "Exposure", value: formatUsd(r.exposure_usd) },
            ],
          }))}
        />
      )}
    </ChartCard>
  );
}

function TopAccounts({ period }: { period: string | undefined }) {
  const query = useTopAccounts(period, 10);
  return (
    <Card title="Accounts with the most breaks" subtitle="Then by USD at stake" bodyClassName="p-0">
      {query.isPending ? (
        <div className="px-4">
          <Loading />
        </div>
      ) : query.isError ? (
        <div className="p-4">
          <ErrorState error={query.error} />
        </div>
      ) : query.data.length === 0 ? (
        <Empty>No accounts with breaks in this period.</Empty>
      ) : (
        <div className={cx(t.wrap, query.isPlaceholderData && "opacity-60")}>
          <table className={t.table}>
            <thead>
              <tr>
                <th scope="col" className={t.th}>
                  GL account
                </th>
                <th scope="col" className={cx(t.th, t.num)}>
                  Transactions
                </th>
                <th scope="col" className={cx(t.th, t.num)}>
                  With breaks
                </th>
                <th scope="col" className={cx(t.th, t.num)}>
                  Highest score
                </th>
                <th scope="col" className={cx(t.th, t.num)}>
                  Exposure
                </th>
                <th scope="col" className={t.th}>
                  Latest
                </th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((a) => (
                <tr key={a.account} className={t.row}>
                  <td className={t.td}>
                    <Link
                      to={transactionsLink({ period, account: a.account, suspicious: true })}
                      className="font-medium text-accent-text hover:underline"
                    >
                      {a.account}
                    </Link>
                  </td>
                  <td className={cx(t.td, t.num)}>{formatNumber(a.transactions)}</td>
                  <td className={cx(t.td, t.num)}>{formatNumber(a.suspicious)}</td>
                  <td className={cx(t.td, t.num)}>{a.max_risk_score ?? DASH}</td>
                  <td className={cx(t.td, t.num)}>{formatUsd(a.exposure_usd)}</td>
                  <td className={cx(t.td, "whitespace-nowrap")}>
                    {formatDate(a.last_transaction_date)}
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

export default function AnalyticsPage() {
  const { period, periods, setPeriod, ready, error } = usePeriod({ defaultLatest: false });
  return (
    <>
      <PageHeader
        title="Analytics"
        description="Where the breaks are: score distribution, break types, segments and accounts."
        actions={<PeriodSelect period={period} periods={periods} onChange={setPeriod} />}
      />
      {error ? (
        <ErrorState error={error} />
      ) : !ready ? (
        <Loading />
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <ScoreDistribution period={period} />
            <BreakRateTrend period={period} />
          </div>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <BreakTypes period={period} />
            <Segments period={period} />
          </div>
          <TopAccounts period={period} />
        </div>
      )}
    </>
  );
}
