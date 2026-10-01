import { type FormEvent, Fragment, useRef, useState } from "react";
import { Link } from "react-router";
import type { Batch } from "../api/client";
import { isRunning, useBatches, useUploadMonth } from "../api/queries";
import { can, useUser } from "../auth/context";
import { Icon } from "../components/Icon";
import {
  Alert,
  Button,
  Card,
  Empty,
  ErrorState,
  Field,
  Input,
  Loading,
  PageHeader,
  Pagination,
  Segmented,
  Spinner,
} from "../components/ui";
import { cx, table as t } from "../lib/cx";
import {
  DASH,
  formatBytes,
  formatDateTime,
  formatDuration,
  formatNumber,
  formatPercent,
  formatPeriod,
  systemName,
} from "../lib/format";
import { transactionsLink } from "../lib/transactionFilters";
import {
  ACCEPT,
  FILE_LABEL,
  toUploadForm,
  UPLOAD_DEFAULTS,
  type UploadErrors,
  type UploadFileField,
  type UploadValues,
  validateUpload,
} from "../lib/uploadForm";

const PAGE_SIZE = 20;

const FILE_HINT: Record<UploadFileField, string> = {
  gl: "The general ledger export",
  fa: "The fixed-asset register export",
  join_map: "Links GL accounts to MA customer and FA keys",
  ma: "The MA server script (read, never run) or an export of its records",
};

function FileField({
  field,
  file,
  error,
  onChange,
}: {
  field: UploadFileField;
  file: File | null;
  error?: string;
  onChange: (file: File | null) => void;
}) {
  const types = ACCEPT[field].join(", ");
  return (
    <Field
      label={FILE_LABEL[field]}
      hint={file ? `${file.name}, ${formatBytes(file.size)}` : `${FILE_HINT[field]} (${types})`}
      error={error}
    >
      {(props) => (
        <input
          {...props}
          name={field}
          type="file"
          accept={ACCEPT[field].join(",")}
          onChange={(event) => onChange(event.target.files?.[0] ?? null)}
          className="block w-full text-sm text-ink-2 file:mr-3 file:h-9 file:cursor-pointer file:rounded-md file:border file:border-line file:bg-surface file:px-3 file:text-sm file:font-medium file:text-ink hover:file:bg-subtle"
        />
      )}
    </Field>
  );
}

function UploadForm() {
  const upload = useUploadMonth();
  const formRef = useRef<HTMLFormElement>(null);
  const [values, setValues] = useState<UploadValues>(UPLOAD_DEFAULTS);
  const [errors, setErrors] = useState<UploadErrors>({});
  const [submitted, setSubmitted] = useState(false);
  // Remounting the form is the only way to clear file inputs.
  const [formKey, setFormKey] = useState(0);

  const update = (patch: Partial<UploadValues>) => {
    const next = { ...values, ...patch };
    setValues(next);
    if (submitted) setErrors(validateUpload(next));
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setSubmitted(true);
    const found = validateUpload(values);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      requestAnimationFrame(() =>
        formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(),
      );
      return;
    }
    upload.mutate(toUploadForm(values), {
      onSuccess: () => {
        setValues(UPLOAD_DEFAULTS);
        setSubmitted(false);
        setFormKey((key) => key + 1);
      },
    });
  };

  return (
    <Card
      title="Load a month"
      subtitle="Loading a month again updates its transactions in place and replaces its join map."
    >
      <form key={formKey} ref={formRef} onSubmit={onSubmit} noValidate className="space-y-4">
        <Field label="Month" hint="YYYYMM, e.g. 202609" error={errors.period} className="max-w-48">
          {(props) => (
            <Input
              {...props}
              name="period"
              inputMode="numeric"
              autoComplete="off"
              placeholder="202609"
              value={values.period}
              onChange={(event) => update({ period: event.target.value })}
            />
          )}
        </Field>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {(["gl", "fa", "join_map"] as const).map((field) => (
            <FileField
              key={field}
              field={field}
              file={values[field]}
              error={errors[field]}
              onChange={(file) => update({ [field]: file })}
            />
          ))}
        </div>
        <div className="space-y-3">
          <p className="mb-1 text-xs font-medium text-ink-2" aria-hidden="true">
            MA records from
          </p>
          <Segmented
            label="MA records from"
            value={values.maSource}
            options={[
              { value: "file", label: "A file" },
              { value: "url", label: "Its REST API" },
            ]}
            onChange={(value) => update({ maSource: value, ma: null })}
          />
          {values.maSource === "file" ? (
            <div className="md:max-w-[calc((100%-2rem)/3)]">
              <FileField
                field="ma"
                file={values.ma}
                error={errors.ma}
                onChange={(file) => update({ ma: file })}
              />
            </div>
          ) : (
            <Field
              label="MA API URL"
              hint="The server only calls hosts on its allow-list (MA_API_ALLOWED_HOSTS)."
              error={errors.maUrl}
              className="max-w-xl"
            >
              {(props) => (
                <Input
                  {...props}
                  name="ma_url"
                  type="url"
                  placeholder="https://ma.example.com/api/records"
                  value={values.maUrl}
                  onChange={(event) => update({ maUrl: event.target.value })}
                />
              )}
            </Field>
          )}
        </div>
        {upload.isError && <Alert title="The upload was refused">{upload.error.message}</Alert>}
        {upload.isSuccess && (
          <Alert tone="success">
            Batch {upload.data.id} for {formatPeriod(upload.data.period)} is queued. The table below
            updates while it loads.
          </Alert>
        )}
        <Button type="submit" variant="primary" busy={upload.isPending}>
          <Icon name="upload" size={16} />
          Upload and load
        </Button>
      </form>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "queued":
      return (
        <span className="inline-flex items-center gap-1.5 text-ink-2">
          <Icon name="clock" size={15} />
          Queued
        </span>
      );
    case "running":
      return (
        <span className="inline-flex items-center gap-1.5 text-ink">
          <Spinner size={14} />
          Loading
        </span>
      );
    case "succeeded":
      return (
        <span className="inline-flex items-center gap-1.5 text-ink">
          <Icon name="check" size={15} className="text-success" />
          Loaded
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1.5 font-medium text-danger">
          <Icon name="alert" size={15} />
          Failed
        </span>
      );
    default:
      return <span>{status}</span>;
  }
}

const count = (value: unknown) => (typeof value === "number" ? formatNumber(value) : DASH);

function BreaksCell({ batch }: { batch: Batch }) {
  const suspicious = batch.summary.suspicious;
  const rate = batch.summary.suspicious_rate;
  if (typeof suspicious !== "number") return <>{DASH}</>;
  if (suspicious === 0) return <>0</>;
  return (
    <Link
      to={transactionsLink({ period: batch.period, suspicious: true })}
      className="text-accent-text hover:underline"
    >
      {formatNumber(suspicious)}
      {typeof rate === "number" && (
        <>
          {" "}
          <span className="text-ink-2">({formatPercent(rate)})</span>
        </>
      )}
    </Link>
  );
}

function Batches() {
  const [page, setPage] = useState(1);
  const query = useBatches(page, PAGE_SIZE);

  if (query.isPending) return <Loading label="Loading batches" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  if (query.data.items.length === 0) return <Empty>No months loaded yet.</Empty>;

  return (
    <>
      <div className={cx(t.wrap, query.isPlaceholderData && "opacity-60")}>
        <table className={t.table}>
          <caption className="sr-only">Load history, newest first</caption>
          <thead>
            <tr>
              <th scope="col" className={t.th}>
                Batch
              </th>
              <th scope="col" className={t.th}>
                Month
              </th>
              <th scope="col" className={t.th}>
                Status
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                GL · MA · FA records
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Transactions
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Scored
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                With breaks
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Took
              </th>
              <th scope="col" className={t.th}>
                Queued
              </th>
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((batch) => {
              const note = typeof batch.summary.note === "string" ? batch.summary.note : null;
              const records = batch.records;
              return (
                <Fragment key={batch.id}>
                  <tr className={t.row}>
                    <td className={cx(t.td, "whitespace-nowrap")}>
                      <details>
                        <summary className="cursor-pointer font-medium text-ink">
                          #{batch.id}
                        </summary>
                        <dl className="mt-1 space-y-0.5 text-xs text-ink-2">
                          {Object.entries(batch.files).map(([source, name]) => (
                            <div key={source}>
                              <dt className="inline font-medium">
                                {source === "join_map" ? "Join map" : systemName(source)}:{" "}
                              </dt>
                              <dd className="inline break-all">{String(name)}</dd>
                            </div>
                          ))}
                        </dl>
                      </details>
                    </td>
                    <td className={cx(t.td, "whitespace-nowrap")}>
                      {formatPeriod(batch.period)}
                      <div className="text-xs text-ink-2">
                        MA from {batch.method === "api" ? "API" : "file"}
                      </div>
                    </td>
                    <td className={cx(t.td, "whitespace-nowrap")}>
                      <StatusBadge status={batch.status} />
                    </td>
                    <td className={cx(t.td, t.num, "whitespace-nowrap")}>
                      {records.gl === undefined
                        ? DASH
                        : `${count(records.gl)} · ${count(records.ma)} · ${count(records.fa)}`}
                    </td>
                    <td className={cx(t.td, t.num)}>
                      {isRunning(batch) ? DASH : formatNumber(batch.transactions_loaded)}
                    </td>
                    <td className={cx(t.td, t.num)}>
                      {isRunning(batch) ? DASH : formatNumber(batch.transactions_scored)}
                    </td>
                    <td className={cx(t.td, t.num, "whitespace-nowrap")}>
                      <BreaksCell batch={batch} />
                    </td>
                    <td className={cx(t.td, t.num, "whitespace-nowrap")}>
                      {formatDuration(batch.duration_ms)}
                    </td>
                    <td className={cx(t.td, "whitespace-nowrap")}>
                      {formatDateTime(batch.created_at)}
                    </td>
                  </tr>
                  {(batch.error || note) && (
                    <tr>
                      <td colSpan={9} className="border-b border-line px-3 pb-3">
                        {batch.error ? (
                          <p className="text-xs text-danger">
                            <span className="font-medium">Error:</span> {batch.error}
                          </p>
                        ) : (
                          <p className="text-xs text-ink-2">{note}</p>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} />
    </>
  );
}

export default function IngestionPage() {
  const user = useUser();
  return (
    <>
      <PageHeader
        title="Data ingestion"
        description="Load a month of GL, MA and FA records with its join map. The server labels the cross-system breaks and scores every transaction with the active model in the background."
      />
      <div className="space-y-5">
        {can.upload(user.role) ? (
          <UploadForm />
        ) : (
          <Alert tone="info">
            Analysts and admins load data. You can follow the load history below.
          </Alert>
        )}
        <Card
          title="Load history"
          subtitle="Newest first; refreshes on its own while a load runs"
          bodyClassName="p-4"
        >
          <Batches />
        </Card>
      </div>
    </>
  );
}
