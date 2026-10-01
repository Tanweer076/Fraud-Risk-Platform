import { Fragment, useState } from "react";
import { Link, useSearchParams } from "react-router";
import type { Review, TransactionSummary } from "../api/client";
import { type ReviewStatus, useBulkApprove, useReviewQueue, useReviews } from "../api/queries";
import { can, useUser } from "../auth/context";
import { BandBadge } from "../components/BandBadge";
import { DecisionForm, ReviewForm } from "../components/ReviewActions";
import { BreakChips } from "../components/TransactionBits";
import {
  Alert,
  Button,
  Card,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Pagination,
  Segmented,
} from "../components/ui";
import { cx, table as t } from "../lib/cx";
import { formatDate, formatDateTime, formatMoney, formatNumber, formatUsd } from "../lib/format";
import { DECISION_LABEL } from "../lib/reviewLabels";

const PAGE_SIZE = 25;

type Tab = "queue" | ReviewStatus;

const TABS: { value: Tab; label: string }[] = [
  { value: "queue", label: "To review" },
  { value: "pending", label: "Awaiting approval" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

function TxLink({ id }: { id: string }) {
  return (
    <Link
      to={`/transactions/${encodeURIComponent(id)}`}
      className="font-mono text-xs font-medium text-accent-text hover:underline"
    >
      {id}
    </Link>
  );
}

function Queue({ page, onPage }: { page: number; onPage: (page: number) => void }) {
  const user = useUser();
  const query = useReviewQueue(page, PAGE_SIZE);
  const [open, setOpen] = useState<string | null>(null);
  const reviewer = can.review(user.role);

  if (query.isPending) return <Loading label="Loading the queue" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  if (query.data.items.length === 0)
    return <Empty>The queue is empty: every flagged transaction has a finding.</Empty>;

  return (
    <>
      <div className={cx(t.wrap, query.isPlaceholderData && "opacity-60")}>
        <table className={t.table}>
          <caption className="sr-only">
            Flagged transactions without a finding, highest priority first
          </caption>
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
              {reviewer && (
                <th scope="col" className={t.th}>
                  <span className="sr-only">Action</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((tx: TransactionSummary) => (
              <Fragment key={tx.transaction_id}>
                <tr
                  className={cx(t.row, "*:align-middle", open === tx.transaction_id && "bg-subtle")}
                >
                  <td className={t.td}>
                    <TxLink id={tx.transaction_id} />
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
                  {reviewer && (
                    <td className={cx(t.td, "text-right")}>
                      <Button
                        size="sm"
                        aria-expanded={open === tx.transaction_id}
                        onClick={() =>
                          setOpen(open === tx.transaction_id ? null : tx.transaction_id)
                        }
                      >
                        {open === tx.transaction_id ? "Close" : "Review"}
                      </Button>
                    </td>
                  )}
                </tr>
                {open === tx.transaction_id && (
                  <tr>
                    <td colSpan={8} className="border-b border-line bg-subtle px-3 py-3">
                      <div className="max-w-xl">
                        <ReviewForm
                          transactionId={tx.transaction_id}
                          onDone={() => setOpen(null)}
                        />
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={onPage} />
    </>
  );
}

function ReviewList({
  status,
  page,
  onPage,
}: {
  status: ReviewStatus;
  page: number;
  onPage: (page: number) => void;
}) {
  const user = useUser();
  const query = useReviews(status, page, PAGE_SIZE);
  const bulk = useBulkApprove();
  const [open, setOpen] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const approver = status === "pending" && can.approve(user.role);

  if (query.isPending) return <Loading label="Loading reviews" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  if (query.data.items.length === 0) {
    return (
      <Empty>
        {status === "pending" ? "Nothing is waiting for approval." : `No ${status} reviews yet.`}
      </Empty>
    );
  }

  const decidable = (review: Review) => approver && review.analyst_id !== user.id;
  const selectable = query.data.items.filter(decidable);
  const toggle = (id: number) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <>
      {approver && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Button
            variant="primary"
            size="sm"
            disabled={selected.size === 0}
            busy={bulk.isPending}
            onClick={() =>
              bulk.mutate(
                { review_ids: [...selected] },
                { onSuccess: () => setSelected(new Set()) },
              )
            }
          >
            Approve {selected.size > 0 ? formatNumber(selected.size) : ""} selected
          </Button>
          {bulk.data && (
            <span className="text-xs text-ink-2" role="status">
              Approved {formatNumber(bulk.data.approved.length)}
              {bulk.data.skipped.length > 0 &&
                `; skipped ${formatNumber(bulk.data.skipped.length)} (${bulk.data.skipped.map((s) => `#${s.id}: ${s.reason}`).join("; ")})`}
            </span>
          )}
          {bulk.isError && <Alert>{bulk.error.message}</Alert>}
        </div>
      )}
      <div className={cx(t.wrap, query.isPlaceholderData && "opacity-60")}>
        <table className={t.table}>
          <thead>
            <tr>
              {approver && (
                <th scope="col" className={t.th}>
                  <input
                    type="checkbox"
                    aria-label="Select all you can approve"
                    className="accent-[var(--accent)]"
                    checked={selectable.length > 0 && selectable.every((r) => selected.has(r.id))}
                    onChange={(event) =>
                      setSelected(
                        event.target.checked ? new Set(selectable.map((r) => r.id)) : new Set(),
                      )
                    }
                    disabled={selectable.length === 0}
                  />
                </th>
              )}
              <th scope="col" className={t.th}>
                Transaction
              </th>
              <th scope="col" className={t.th}>
                Finding
              </th>
              <th scope="col" className={t.th}>
                Analyst
              </th>
              <th scope="col" className={t.th}>
                Note
              </th>
              <th scope="col" className={t.th}>
                Submitted
              </th>
              {status !== "pending" && (
                <th scope="col" className={t.th}>
                  Decided by
                </th>
              )}
              {approver && (
                <th scope="col" className={t.th}>
                  <span className="sr-only">Action</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((review) => (
              <Fragment key={review.id}>
                <tr className={cx(t.row, "*:align-middle", open === review.id && "bg-subtle")}>
                  {approver && (
                    <td className={t.td}>
                      <input
                        type="checkbox"
                        aria-label={`Select review ${review.id}`}
                        className="accent-[var(--accent)]"
                        checked={selected.has(review.id)}
                        onChange={() => toggle(review.id)}
                        disabled={!decidable(review)}
                        title={decidable(review) ? undefined : "You can't approve your own finding"}
                      />
                    </td>
                  )}
                  <td className={t.td}>
                    <TxLink id={review.transaction_id} />
                  </td>
                  <td className={t.td}>{DECISION_LABEL[review.decision] ?? review.decision}</td>
                  <td className={t.td}>{review.analyst_email ?? `user ${review.analyst_id}`}</td>
                  <td className={cx(t.td, "max-w-xs text-ink-2")}>{review.note || "—"}</td>
                  <td className={cx(t.td, "whitespace-nowrap")}>
                    {formatDateTime(review.created_at)}
                  </td>
                  {status !== "pending" && (
                    <td className={t.td}>
                      {review.approver_email ?? "—"}
                      {review.approver_note && (
                        <div className="text-xs text-ink-2">“{review.approver_note}”</div>
                      )}
                    </td>
                  )}
                  {approver && (
                    <td className={cx(t.td, "text-right")}>
                      {decidable(review) ? (
                        <Button
                          size="sm"
                          aria-expanded={open === review.id}
                          onClick={() => setOpen(open === review.id ? null : review.id)}
                        >
                          {open === review.id ? "Close" : "Decide"}
                        </Button>
                      ) : (
                        <span className="text-xs text-ink-3">Your finding</span>
                      )}
                    </td>
                  )}
                </tr>
                {open === review.id && (
                  <tr>
                    <td colSpan={8} className="border-b border-line bg-subtle px-3 py-3">
                      <div className="max-w-xl">
                        <DecisionForm review={review} onDone={() => setOpen(null)} />
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={onPage} />
    </>
  );
}

export default function ReviewsPage() {
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((item) => item.value === params.get("tab"))?.value ?? "queue") as Tab;
  const page = Math.max(1, Number(params.get("page")) || 1);
  const go = (next: { tab?: Tab; page?: number }) =>
    setParams({
      tab: next.tab ?? tab,
      ...(next.page && next.page > 1 ? { page: String(next.page) } : {}),
    });

  return (
    <>
      <PageHeader
        title="Review queue"
        description="Flagged transactions, highest priority first. An analyst records a finding, then an approver confirms or rejects it; nobody approves their own."
      />
      <div className="mb-4">
        <Segmented
          label="Review stage"
          value={tab}
          options={TABS}
          onChange={(value) => go({ tab: value, page: 1 })}
        />
      </div>
      <Card bodyClassName="p-4">
        {tab === "queue" ? (
          <Queue page={page} onPage={(p) => go({ page: p })} />
        ) : (
          <ReviewList key={tab} status={tab} page={page} onPage={(p) => go({ page: p })} />
        )}
      </Card>
    </>
  );
}
