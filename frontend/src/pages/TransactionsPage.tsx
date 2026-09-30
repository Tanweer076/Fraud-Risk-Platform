import { useState } from "react";
import { Link } from "react-router";
import type { Band, TransactionSummary } from "../api/client";
import { downloadTransactionsCsv, useSummary, useTransactions } from "../api/queries";
import { BandBadge, BandIcon } from "../components/BandBadge";
import { SelectFilter, TextFilter } from "../components/Filters";
import { Icon } from "../components/Icon";
import { BreakChips, ReviewOutcome, SystemsPresence } from "../components/TransactionBits";
import {
  Alert,
  Button,
  Card,
  Empty,
  ErrorState,
  Input,
  Loading,
  PageHeader,
  Pagination,
} from "../components/ui";
import { BAND_LABEL, BANDS } from "../lib/bands";
import { cx, table as t } from "../lib/cx";
import { breakLabel, DASH, formatDate, formatMoney, formatPeriod, formatUsd } from "../lib/format";
import { CURRENCIES, COUNTRIES } from "../lib/scoreForm";
import { BREAK_TYPES, useTransactionFilters } from "../lib/transactionFilters";

const PAGE_SIZE = 50;

type SortKey = "priority" | "risk_score" | "transaction_date" | "amount" | "exposure_usd";

function SortHeader({
  label,
  field,
  sort,
  onSort,
  numeric,
}: {
  label: string;
  field: SortKey;
  sort: string;
  onSort: (sort: string) => void;
  numeric?: boolean;
}) {
  const primary = sort.split(",")[0];
  const direction =
    primary === field ? "ascending" : primary === `-${field}` ? "descending" : undefined;
  const next = direction === "descending" ? field : `-${field}`;
  return (
    <th scope="col" aria-sort={direction ?? "none"} className={cx(t.th, numeric && t.num)}>
      <button
        type="button"
        onClick={() => onSort(next)}
        className={cx("inline-flex items-center gap-1 hover:text-ink", direction && "text-ink")}
      >
        {label}
        <span aria-hidden="true" className="text-[10px]">
          {direction === "ascending" ? "▲" : direction === "descending" ? "▼" : "↕"}
        </span>
      </button>
    </th>
  );
}

function Row({ tx }: { tx: TransactionSummary }) {
  return (
    <tr className={t.row}>
      <td className={t.td}>
        <Link
          to={`/transactions/${encodeURIComponent(tx.transaction_id)}`}
          className="font-mono text-xs font-medium text-accent-text hover:underline"
        >
          {tx.transaction_id}
        </Link>
        <div className="text-xs text-ink-3">{formatPeriod(tx.period)}</div>
      </td>
      <td className={cx(t.td, "whitespace-nowrap")}>{formatDate(tx.transaction_date)}</td>
      <td className={cx(t.td, "whitespace-nowrap")}>{tx.gl_account_id ?? DASH}</td>
      <td className={cx(t.td, t.num, "whitespace-nowrap")}>
        {formatMoney(tx.amount, tx.currency)}
      </td>
      <td className={t.td}>
        <SystemsPresence tx={tx} />
      </td>
      <td className={t.td}>
        <BreakChips breaks={tx.break_types} limit={2} />
      </td>
      <td className={t.td}>
        <BandBadge band={tx.risk_band} score={tx.risk_score} />
      </td>
      <td className={cx(t.td, t.num)}>{tx.priority ?? DASH}</td>
      <td className={cx(t.td, t.num, "whitespace-nowrap")}>
        {tx.exposure_usd ? formatUsd(tx.exposure_usd) : DASH}
      </td>
      <td className={t.td}>
        <ReviewOutcome outcome={tx.review_outcome} />
      </td>
    </tr>
  );
}

export default function TransactionsPage() {
  const { filters, sort, page, update, clear, active } = useTransactionFilters();
  const summary = useSummary();
  const query = useTransactions(filters, sort, page, PAGE_SIZE);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const toggleBand = (band: Band) => {
    const current = filters.band ?? [];
    update({
      band: current.includes(band) ? current.filter((b) => b !== band) : [...current, band],
    });
  };

  const exportCsv = async () => {
    setExporting(true);
    setExportError(null);
    try {
      await downloadTransactionsCsv(filters);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Transactions"
        description="Every linked transaction with its latest risk score. Sorted by priority by default, so large, risky breaks come first."
        actions={
          <Button onClick={exportCsv} busy={exporting}>
            <Icon name="download" size={16} />
            Export CSV
          </Button>
        }
      />
      {exportError && (
        <div className="mb-4">
          <Alert title="Export failed">{exportError}</Alert>
        </div>
      )}

      <Card className="mb-4" bodyClassName="p-4 space-y-3">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
          <SelectFilter
            label="Period"
            value={filters.period ?? ""}
            onChange={(period) => update({ period })}
          >
            <option value="">All periods</option>
            {(summary.data?.periods ?? []).map((period) => (
              <option key={period} value={period}>
                {formatPeriod(period)}
              </option>
            ))}
          </SelectFilter>
          <SelectFilter
            label="Break type"
            value={filters.break_type ?? ""}
            onChange={(breakType) => update({ break_type: breakType })}
          >
            <option value="">Any</option>
            {BREAK_TYPES.map((code) => (
              <option key={code} value={code}>
                {breakLabel(code)}
              </option>
            ))}
          </SelectFilter>
          <SelectFilter
            label="Currency"
            value={filters.currency ?? ""}
            onChange={(currency) => update({ currency })}
          >
            <option value="">Any</option>
            {CURRENCIES.map((code) => (
              <option key={code}>{code}</option>
            ))}
          </SelectFilter>
          <SelectFilter
            label="Country"
            value={filters.country ?? ""}
            onChange={(country) => update({ country })}
          >
            <option value="">Any</option>
            {COUNTRIES.map((code) => (
              <option key={code}>{code}</option>
            ))}
          </SelectFilter>
          <SelectFilter
            label="Breaks"
            value={filters.suspicious === undefined ? "" : String(filters.suspicious)}
            onChange={(value) => update({ suspicious: value })}
          >
            <option value="">Any</option>
            <option value="true">With breaks</option>
            <option value="false">Clean</option>
          </SelectFilter>
          <SelectFilter
            label="Reviewed"
            value={filters.reviewed === undefined ? "" : String(filters.reviewed)}
            onChange={(value) => update({ reviewed: value })}
          >
            <option value="">Any</option>
            <option value="true">Reviewed</option>
            <option value="false">Not reviewed</option>
          </SelectFilter>
          <TextFilter
            label="Search ID or description"
            value={filters.search}
            onApply={(search) => update({ search })}
            className="lg:col-span-2"
          />
          <TextFilter
            label="GL account"
            value={filters.account}
            placeholder="ACC0001"
            onApply={(account) => update({ account })}
          />
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-2">From</span>
            <Input
              type="date"
              value={filters.date_from ?? ""}
              onChange={(e) => update({ date_from: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-2">To</span>
            <Input
              type="date"
              value={filters.date_to ?? ""}
              onChange={(e) => update({ date_to: e.target.value })}
            />
          </label>
          <TextFilter
            label="Min score"
            value={filters.min_score === undefined ? undefined : String(filters.min_score)}
            placeholder="0–100"
            onApply={(minScore) => update({ min_score: minScore })}
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div role="group" aria-label="Risk band" className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium text-ink-2">Band</span>
            {BANDS.map((band) => {
              const on = filters.band?.includes(band) ?? false;
              return (
                <button
                  key={band}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleBand(band)}
                  className={cx(
                    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs",
                    on
                      ? "border-ink/40 bg-subtle font-medium text-ink"
                      : "border-line text-ink-2 hover:bg-subtle",
                  )}
                >
                  <BandIcon band={band} size={12} />
                  {BAND_LABEL[band]}
                </button>
              );
            })}
          </div>
          {active && (
            <Button size="sm" variant="ghost" onClick={clear}>
              <Icon name="close" size={14} />
              Clear filters
            </Button>
          )}
        </div>
      </Card>

      <Card bodyClassName="p-0">
        {query.isPending ? (
          <div className="px-4">
            <Loading label="Loading transactions" />
          </div>
        ) : query.isError ? (
          <div className="p-4">
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          </div>
        ) : query.data.items.length === 0 ? (
          <Empty>
            {active ? (
              "No transactions match these filters."
            ) : (
              <>
                No transactions yet. Load a month on the{" "}
                <Link to="/ingestion" className="text-accent-text underline">
                  Data ingestion
                </Link>{" "}
                page.
              </>
            )}
          </Empty>
        ) : (
          <div
            className={cx(t.wrap, "transition-opacity", query.isPlaceholderData && "opacity-60")}
          >
            <table className={t.table}>
              <caption className="sr-only">
                Transactions, {sort.startsWith("-priority") ? "highest priority first" : "sorted"}
              </caption>
              <thead>
                <tr>
                  <th scope="col" className={t.th}>
                    Transaction
                  </th>
                  <SortHeader
                    label="Date"
                    field="transaction_date"
                    sort={sort}
                    onSort={(s) => update({ sort: s })}
                  />
                  <th scope="col" className={t.th}>
                    GL account
                  </th>
                  <SortHeader
                    label="Amount"
                    field="amount"
                    sort={sort}
                    onSort={(s) => update({ sort: s })}
                    numeric
                  />
                  <th scope="col" className={t.th}>
                    Systems
                  </th>
                  <th scope="col" className={t.th}>
                    Breaks
                  </th>
                  <SortHeader
                    label="Risk"
                    field="risk_score"
                    sort={sort}
                    onSort={(s) => update({ sort: s })}
                  />
                  <SortHeader
                    label="Priority"
                    field="priority"
                    sort={sort}
                    onSort={(s) => update({ sort: s })}
                    numeric
                  />
                  <SortHeader
                    label="Exposure"
                    field="exposure_usd"
                    sort={sort}
                    onSort={(s) => update({ sort: s })}
                    numeric
                  />
                  <th scope="col" className={t.th}>
                    Review
                  </th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((tx) => (
                  <Row key={tx.transaction_id} tx={tx} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {query.data && (
          <div className="px-4 pb-3">
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={query.data.total}
              onPage={(next) => update({ page: next })}
            />
          </div>
        )}
      </Card>
    </>
  );
}
