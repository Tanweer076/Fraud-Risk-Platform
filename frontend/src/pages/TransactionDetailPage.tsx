import { Link, useParams } from "react-router";
import { ApiError, type SystemRecord, type TransactionDetail } from "../api/client";
import { useTransaction } from "../api/queries";
import { can, useUser } from "../auth/context";
import { BandBadge } from "../components/BandBadge";
import { FactorBars } from "../components/FactorBars";
import { Icon } from "../components/Icon";
import { DecisionForm, ReviewForm, ReviewSummary } from "../components/ReviewActions";
import { RiskGauge } from "../components/RiskGauge";
import { BreakChips } from "../components/TransactionBits";
import { Alert, Card, Chip, Empty, ErrorState, Loading, PageHeader } from "../components/ui";
import { type FieldKey, FIELDS, mismatches, SYSTEMS } from "../lib/compare";
import { cx, table as t } from "../lib/cx";
import {
  DASH,
  formatDate,
  formatDateTime,
  formatDecimal,
  formatMoney,
  formatPeriod,
  formatUsd,
  systemName,
} from "../lib/format";

function display(key: FieldKey, record: SystemRecord) {
  if (key === "amount") return formatMoney(record.amount, record.currency);
  if (key === "transaction_date") return formatDate(record.transaction_date);
  const value = record[key];
  return value == null || value === "" ? DASH : String(value);
}

function RecordsTable({ tx }: { tx: TransactionDetail }) {
  return (
    <div className={t.wrap}>
      <table className={t.table}>
        <caption className="sr-only">
          Each system's record of this transaction; differences are marked
        </caption>
        <thead>
          <tr>
            <th scope="col" className={t.th}>
              Field
            </th>
            {SYSTEMS.map((s) => (
              <th key={s} scope="col" className={t.th}>
                {systemName(s)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {FIELDS.map((field) => {
            const differs = mismatches(tx, field.key);
            return (
              <tr key={field.key}>
                <th scope="row" className={cx(t.td, "text-xs font-medium text-ink-2")}>
                  {field.label}
                </th>
                {SYSTEMS.map((s) => {
                  const record = tx.systems[s];
                  if (!record) {
                    return (
                      <td key={s} className={cx(t.td, "text-xs text-danger")}>
                        Not in {systemName(s)}
                      </td>
                    );
                  }
                  const off = differs.has(s);
                  return (
                    <td
                      key={s}
                      className={cx(
                        t.td,
                        off &&
                          "bg-[color-mix(in_oklab,var(--status-critical)_10%,transparent)] font-medium",
                      )}
                    >
                      <span className="inline-flex items-center gap-1">
                        {off && (
                          <Icon
                            name="alert"
                            size={13}
                            className="shrink-0 text-danger"
                            aria-label="Differs"
                          />
                        )}
                        {display(field.key, record)}
                      </span>
                    </td>
                  );
                })}
              </tr>
            );
          })}
          <tr>
            <th scope="row" className={cx(t.td, "text-xs font-medium text-ink-2")}>
              Rules broken
            </th>
            {SYSTEMS.map((s) => {
              const violations = tx.systems[s]?.rule_violations ?? [];
              return (
                <td key={s} className={t.td}>
                  {violations.length ? (
                    <span className="flex flex-wrap gap-1">
                      {violations.map((code) => (
                        <Chip key={code} className="border-critical/50 text-ink">
                          {code}
                        </Chip>
                      ))}
                    </span>
                  ) : (
                    <span className="text-xs text-ink-3">{tx.systems[s] ? "None" : DASH}</span>
                  )}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
      <p className="mt-2 text-xs text-ink-2">
        Join map: GL account {tx.gl_account_id ?? DASH}{" "}
        {tx.gl_account_mapped ? "is mapped" : "is not in the join map"}
        {tx.expected_ma_key && ` · expected MA key ${tx.expected_ma_key}`}
        {tx.expected_fa_key && ` · expected FA key ${tx.expected_fa_key}`}
      </p>
    </div>
  );
}

function Reviews({ tx }: { tx: TransactionDetail }) {
  const user = useUser();
  const open = tx.reviews.find((r) => r.status === "pending" || r.status === "approved");
  const pending = tx.reviews.find((r) => r.status === "pending");
  const flagged = (tx.risk_score ?? 0) > 0;

  return (
    <Card
      title="Review"
      subtitle="An analyst records a finding; a different person approves or rejects it."
    >
      <div className="space-y-4">
        {tx.reviews.length > 0 && (
          <ol className="space-y-3">
            {tx.reviews.map((review) => (
              <li key={review.id} className="border-l-2 border-line pl-3">
                <ReviewSummary review={review} />
              </li>
            ))}
          </ol>
        )}
        {pending &&
          can.approve(user.role) &&
          (pending.analyst_id === user.id ? (
            <Alert tone="info">You made this finding, so someone else has to approve it.</Alert>
          ) : (
            <DecisionForm review={pending} />
          ))}
        {pending && !can.approve(user.role) && pending.analyst_id === user.id && (
          <p className="text-xs text-ink-2">Waiting for an approver.</p>
        )}
        {!open && flagged && can.review(user.role) && (
          <ReviewForm transactionId={tx.transaction_id} />
        )}
        {!open && !can.review(user.role) && tx.reviews.length === 0 && (
          <Empty>Not reviewed yet.</Empty>
        )}
      </div>
    </Card>
  );
}

export default function TransactionDetailPage() {
  const { transactionId = "" } = useParams();
  const query = useTransaction(transactionId);

  if (query.isPending) return <Loading label="Loading transaction" />;
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404) {
      return (
        <>
          <PageHeader
            title="Transaction not found"
            description={`No transaction has the ID ${transactionId}.`}
          />
          <Link to="/transactions" className="font-medium text-accent-text underline">
            Back to transactions
          </Link>
        </>
      );
    }
    return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  }

  const tx = query.data;
  const latest = tx.predictions[0];
  return (
    <>
      <Link
        to="/transactions"
        className="mb-3 inline-flex items-center gap-1 text-xs text-ink-2 hover:text-ink"
      >
        <Icon name="back" size={14} />
        Transactions
      </Link>
      <PageHeader
        title={<span className="font-mono">{tx.transaction_id}</span>}
        description={`${formatPeriod(tx.period)} · ${tx.description ?? "No description"} · loaded ${tx.source === "api" ? "through the API" : "in a batch"}`}
        actions={<BandBadge band={tx.risk_band} score={tx.risk_score} className="text-sm" />}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-5">
          <Card
            title="Records by system"
            subtitle="The same transaction as GL, MA and FA recorded it"
          >
            <RecordsTable tx={tx} />
          </Card>

          <Card title="Why it was flagged">
            <h3 className="mb-2 text-xs font-medium text-ink-2">Checks that failed</h3>
            {latest && latest.rule_hits.length > 0 ? (
              <ul className="mb-5 space-y-1.5">
                {latest.rule_hits.map((hit, index) => (
                  <li key={index} className="flex gap-2 text-sm text-ink">
                    <Icon name="alert" size={16} className="mt-0.5 shrink-0 text-danger" />
                    {hit.reason}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mb-5 text-sm text-ink-2">
                None: the systems agree and every rule passes.
              </p>
            )}
            <h3 className="mb-2 text-xs font-medium text-ink-2">Model explanation</h3>
            {latest && latest.top_factors.length > 0 ? (
              <FactorBars factors={latest.top_factors} />
            ) : (
              <p className="text-sm text-ink-2">
                Not explained. Month loads only explain scores at or above the explanation
                threshold; score it again on the Score page to see the factors.
              </p>
            )}
          </Card>

          <Card title="Score history" bodyClassName="p-0">
            {tx.predictions.length === 0 ? (
              <Empty>Not scored yet.</Empty>
            ) : (
              <div className={t.wrap}>
                <table className={t.table}>
                  <thead>
                    <tr>
                      <th scope="col" className={t.th}>
                        Scored
                      </th>
                      <th scope="col" className={t.th}>
                        Risk
                      </th>
                      <th scope="col" className={cx(t.th, t.num)}>
                        Priority
                      </th>
                      <th scope="col" className={cx(t.th, t.num)}>
                        Probability
                      </th>
                      <th scope="col" className={t.th}>
                        Breaks
                      </th>
                      <th scope="col" className={t.th}>
                        Model, source
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {tx.predictions.map((p) => (
                      <tr key={p.id}>
                        <td className={cx(t.td, "whitespace-nowrap")}>
                          {formatDateTime(p.created_at)}
                        </td>
                        <td className={t.td}>
                          <BandBadge band={p.risk_band} score={p.risk_score} />
                        </td>
                        <td className={cx(t.td, t.num)}>{p.priority}</td>
                        <td className={cx(t.td, t.num)}>{formatDecimal(p.probability, 3)}</td>
                        <td className={t.td}>
                          <BreakChips breaks={p.break_types} limit={2} />
                        </td>
                        <td className={cx(t.td, "whitespace-nowrap")}>
                          {p.model_version}
                          <div className="text-xs text-ink-2">
                            {p.source === "api" ? "Scored through the API" : "Loaded in a batch"}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="min-w-0 space-y-5">
          <Card title="Risk">
            {tx.risk_score != null ? (
              <RiskGauge score={tx.risk_score} />
            ) : (
              <Empty>Not scored.</Empty>
            )}
            <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-ink-2">Priority</dt>
                <dd className="font-semibold text-ink">{tx.priority ?? DASH}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-2">Exposure</dt>
                <dd className="font-semibold text-ink">
                  {tx.exposure_usd ? formatUsd(tx.exposure_usd) : DASH}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-2">Breaks</dt>
                <dd className="mt-0.5">
                  <BreakChips breaks={tx.break_types} limit={9} />
                </dd>
              </div>
              <div>
                <dt className="text-xs text-ink-2">Scored</dt>
                <dd className="text-ink">{formatDateTime(tx.scored_at)}</dd>
              </div>
            </dl>
          </Card>
          <Reviews tx={tx} />
        </div>
      </div>
    </>
  );
}
