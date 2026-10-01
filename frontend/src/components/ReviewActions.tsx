import { useState } from "react";
import type { Review } from "../api/client";
import { useCreateReview, useDecideReview } from "../api/queries";
import { cx } from "../lib/cx";
import { formatDateTime } from "../lib/format";
import { DECISION_LABEL, STATUS_LABEL } from "../lib/reviewLabels";
import { Alert, Button, Textarea } from "./ui";

/** The analyst's finding on a flagged transaction (the "maker" step). */
export function ReviewForm({
  transactionId,
  onDone,
}: {
  transactionId: string;
  onDone?: () => void;
}) {
  const create = useCreateReview();
  const [decision, setDecision] = useState<"confirmed" | "false_positive" | null>(null);
  const [note, setNote] = useState("");

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (!decision) return;
        create.mutate(
          { transaction_id: transactionId, decision, note: note.trim() },
          { onSuccess: () => onDone?.() },
        );
      }}
    >
      <fieldset>
        <legend className="mb-1.5 text-xs font-medium text-ink-2">Your finding</legend>
        <div className="flex flex-wrap gap-2">
          {(["confirmed", "false_positive"] as const).map((value) => (
            <label
              key={value}
              className={cx(
                "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm",
                decision === value
                  ? "border-accent bg-subtle text-ink"
                  : "border-line text-ink-2 hover:bg-subtle",
              )}
            >
              <input
                type="radio"
                name={`decision-${transactionId}`}
                value={value}
                checked={decision === value}
                onChange={() => setDecision(value)}
                className="accent-[var(--accent)]"
              />
              {DECISION_LABEL[value]}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-ink-2">Note (optional)</span>
        <Textarea
          value={note}
          maxLength={2000}
          onChange={(event) => setNote(event.target.value)}
          placeholder="What you checked and what you found"
        />
      </label>
      {create.isError && <Alert>{create.error.message}</Alert>}
      <Button type="submit" variant="primary" disabled={!decision} busy={create.isPending}>
        Submit for approval
      </Button>
    </form>
  );
}

/** Approve or reject someone else's finding (the "checker" step). A rejection needs a reason. */
export function DecisionForm({ review, onDone }: { review: Review; onDone?: () => void }) {
  const decide = useDecideReview();
  const [note, setNote] = useState("");
  const [needsNote, setNeedsNote] = useState(false);

  const submit = (action: "approve" | "reject") => {
    if (action === "reject" && !note.trim()) {
      setNeedsNote(true);
      return;
    }
    decide.mutate({ id: review.id, action, note: note.trim() }, { onSuccess: () => onDone?.() });
  };

  return (
    <div className="space-y-2">
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-ink-2">
          Approver note (required to reject)
        </span>
        <Textarea
          value={note}
          maxLength={2000}
          aria-invalid={needsNote && !note.trim() ? true : undefined}
          onChange={(event) => {
            setNote(event.target.value);
            setNeedsNote(false);
          }}
        />
      </label>
      {needsNote && !note.trim() && (
        <p className="text-xs text-danger">Say why you are rejecting it.</p>
      )}
      {decide.isError && <Alert>{decide.error.message}</Alert>}
      <div className="flex gap-2">
        <Button
          variant="primary"
          onClick={() => submit("approve")}
          busy={decide.isPending && decide.variables?.action === "approve"}
        >
          Approve
        </Button>
        <Button
          variant="danger"
          onClick={() => submit("reject")}
          busy={decide.isPending && decide.variables?.action === "reject"}
        >
          Reject
        </Button>
      </div>
    </div>
  );
}

export function ReviewSummary({ review }: { review: Review }) {
  return (
    <div className="text-sm">
      <p className="text-ink">
        <span className="font-medium">{DECISION_LABEL[review.decision] ?? review.decision}</span>
        <span className="text-ink-2">
          {" "}
          by {review.analyst_email ?? `user ${review.analyst_id}`}
        </span>
        <span className="text-ink-3"> · {formatDateTime(review.created_at)}</span>
      </p>
      {review.note && <p className="mt-0.5 text-ink-2">“{review.note}”</p>}
      <p className="mt-1 text-xs text-ink-2">
        {STATUS_LABEL[review.status] ?? review.status}
        {review.approver_email && ` by ${review.approver_email}`}
        {review.decided_at && ` · ${formatDateTime(review.decided_at)}`}
      </p>
      {review.approver_note && (
        <p className="mt-0.5 text-xs text-ink-2">“{review.approver_note}”</p>
      )}
    </div>
  );
}
