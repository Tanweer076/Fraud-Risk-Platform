import { useSearchParams } from "react-router";
import type { ModelEvaluation, ModelVersion } from "../api/client";
import { useActivateModel, useModelEvaluation, useModels, useSyncModels } from "../api/queries";
import { can, useUser } from "../auth/context";
import { BandIcon } from "../components/BandBadge";
import { ChartCard } from "../components/charts/ChartCard";
import { CurveChart } from "../components/charts/Charts";
import { HBarChart } from "../components/charts/HBarChart";
import { Icon } from "../components/Icon";
import {
  Alert,
  Button,
  Card,
  Chip,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
} from "../components/ui";
import { BAND_LABEL, isBand } from "../lib/bands";
import { cx, table as t } from "../lib/cx";
import {
  breakLabel,
  DASH,
  formatDateTime,
  formatDecimal,
  formatNumber,
  formatPercent,
  formatPeriod,
  sentenceCase,
} from "../lib/format";

// The evaluation is stored as the model's metadata JSON; these are the parts this page reads.
interface Metrics {
  n: number;
  positives: number;
  pr_auc: number;
  roc_auc: number;
  precision: number;
  recall: number;
  f1: number;
  brier?: number;
}
interface Candidate {
  model: string;
  features: string;
  threshold: number;
  test: Metrics;
}
interface Confusion {
  tp: number;
  fp: number;
  tn: number;
  fn: number;
}
interface Champion {
  model: string;
  threshold: number;
  test?: Metrics;
  test_hybrid_high_or_above?: Metrics;
  test_recall_by_break_type?: Record<
    "model_only" | "with_rule_floors",
    Record<string, { n: number; recall: number }>
  >;
}
interface Evaluation {
  period: string;
  pr_curve: { precision: number; recall: number; threshold: number }[];
  roc_curve: { fpr: number; tpr: number; threshold: number }[];
  calibration: {
    bin_from: number;
    bin_to: number;
    predicted: number;
    observed: number;
    count: number;
  }[];
  confusion_model: Confusion;
  confusion_with_rule_floors: Confusion;
  feature_importance: { feature: string; mean_abs_contribution: number }[];
}

function VersionsTable({
  versions,
  selected,
  onSelect,
}: {
  versions: ModelVersion[];
  selected?: number;
  onSelect: (id: number) => void;
}) {
  const user = useUser();
  const activate = useActivateModel();
  return (
    <Card
      title="Model versions"
      subtitle="Exactly one version scores new transactions"
      bodyClassName="p-0"
    >
      {activate.isError && (
        <div className="p-4 pb-0">
          <Alert>{activate.error.message}</Alert>
        </div>
      )}
      <div className={t.wrap}>
        <table className={t.table}>
          <thead>
            <tr>
              <th scope="col" className={t.th}>
                Version
              </th>
              <th scope="col" className={t.th}>
                Algorithm
              </th>
              <th scope="col" className={t.th}>
                Trained on
              </th>
              <th scope="col" className={t.th}>
                Tested on
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Features
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Test PR-AUC
              </th>
              <th scope="col" className={t.th}>
                Trained
              </th>
              <th scope="col" className={t.th}>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => {
              const test = (v.metrics as { test?: Metrics }).test;
              return (
                <tr key={v.id} className={cx(t.row, v.id === selected && "bg-subtle")}>
                  <td className={t.td}>
                    <button
                      type="button"
                      onClick={() => onSelect(v.id)}
                      aria-pressed={v.id === selected}
                      className="font-medium text-accent-text hover:underline"
                    >
                      {v.version}
                    </button>
                  </td>
                  <td className={t.td}>{sentenceCase(v.algorithm)}</td>
                  <td className={t.td}>{v.train_periods.map(formatPeriod).join(", ")}</td>
                  <td className={t.td}>{formatPeriod(v.test_period)}</td>
                  <td className={cx(t.td, t.num)}>{v.n_features}</td>
                  <td className={cx(t.td, t.num)}>{formatDecimal(test?.pr_auc, 3)}</td>
                  <td className={cx(t.td, "whitespace-nowrap")}>{formatDateTime(v.trained_at)}</td>
                  <td className={t.td}>
                    {v.is_active ? (
                      <Chip className="text-ink">
                        <Icon name="check" size={12} />
                        Active
                      </Chip>
                    ) : can.manageModels(user.role) ? (
                      <Button
                        size="sm"
                        onClick={() => activate.mutate(v.id)}
                        busy={activate.isPending && activate.variables === v.id}
                      >
                        Activate
                      </Button>
                    ) : (
                      <span className="text-xs text-ink-3">Inactive</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Headline({ champion, evaluation }: { champion: Champion; evaluation: Evaluation | null }) {
  const model = champion.test;
  const hybrid = champion.test_hybrid_high_or_above;
  const tiles = [
    { label: "Model alone: precision", value: formatPercent(model?.precision) },
    { label: "Model alone: recall", value: formatPercent(model?.recall) },
    { label: "With rule floors: precision", value: formatPercent(hybrid?.precision) },
    { label: "With rule floors: recall", value: formatPercent(hybrid?.recall) },
  ];
  return (
    <Card
      title={`Champion: ${sentenceCase(champion.model)}`}
      subtitle={`Tested on ${formatPeriod(evaluation?.period)}${model ? `, ${formatNumber(model.n)} transactions of which ${formatNumber(model.positives)} have breaks` : ""}. The risk score takes the higher of the model's score and the rule floor of any break found, so a break the model misses still scores high.`}
    >
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {tiles.map((tile) => (
          <div key={tile.label}>
            <dt className="text-xs text-ink-2">{tile.label}</dt>
            <dd className="text-2xl font-semibold text-ink">{tile.value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-ink-2">Flagged means a score in the high band or above.</p>
    </Card>
  );
}

function Comparison({ candidates, champion }: { candidates: Candidate[]; champion: Champion }) {
  return (
    <Card title="Models compared" subtitle="Scores on the held-out test month" bodyClassName="p-0">
      <div className={t.wrap}>
        <table className={t.table}>
          <thead>
            <tr>
              <th scope="col" className={t.th}>
                Model
              </th>
              <th scope="col" className={t.th}>
                Features
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                PR-AUC
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                ROC-AUC
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Precision
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Recall
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                F1
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Brier
              </th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c) => {
              const isChampion = c.model === champion.model;
              return (
                <tr key={`${c.model}-${c.features}`} className={cx(isChampion && "bg-subtle")}>
                  <td className={cx(t.td, "font-medium")}>
                    {sentenceCase(c.model)}
                    {isChampion && <Chip className="ml-2 text-ink">Champion</Chip>}
                  </td>
                  <td className={cx(t.td, "text-ink-2")}>{c.features}</td>
                  <td className={cx(t.td, t.num)}>{formatDecimal(c.test.pr_auc)}</td>
                  <td className={cx(t.td, t.num)}>{formatDecimal(c.test.roc_auc)}</td>
                  <td className={cx(t.td, t.num)}>{formatDecimal(c.test.precision)}</td>
                  <td className={cx(t.td, t.num)}>{formatDecimal(c.test.recall)}</td>
                  <td className={cx(t.td, t.num)}>{formatDecimal(c.test.f1)}</td>
                  <td className={cx(t.td, t.num)}>{formatDecimal(c.test.brier)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ConfusionTable({ title, matrix }: { title: string; matrix: Confusion }) {
  const cell = "border border-line px-3 py-2 text-right tabular-nums";
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium text-ink-2">{title}</h3>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <td />
            <th scope="col" className="px-3 pb-1 text-right text-xs font-medium text-ink-2">
              Flagged
            </th>
            <th scope="col" className="px-3 pb-1 text-right text-xs font-medium text-ink-2">
              Not flagged
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row" className="pr-2 text-left text-xs font-medium text-ink-2">
              Has breaks
            </th>
            <td className={cx(cell, "font-semibold")}>{formatNumber(matrix.tp)}</td>
            <td className={cell}>{formatNumber(matrix.fn)}</td>
          </tr>
          <tr>
            <th scope="row" className="pr-2 text-left text-xs font-medium text-ink-2">
              Clean
            </th>
            <td className={cell}>{formatNumber(matrix.fp)}</td>
            <td className={cx(cell, "font-semibold")}>{formatNumber(matrix.tn)}</td>
          </tr>
        </tbody>
      </table>
      <p className="mt-1 text-xs text-ink-2">
        Missed: {formatNumber(matrix.fn)} · false alarms: {formatNumber(matrix.fp)}
      </p>
    </div>
  );
}

function RecallByBreak({ champion }: { champion: Champion }) {
  const recall = champion.test_recall_by_break_type;
  if (!recall) return null;
  const types = Object.keys(recall.model_only).sort(
    (a, b) => recall.model_only[b].n - recall.model_only[a].n,
  );
  return (
    <Card
      title="Breaks caught, by type"
      subtitle="Share of each break type scored high or above on the test month"
      bodyClassName="p-0"
    >
      <div className={t.wrap}>
        <table className={t.table}>
          <thead>
            <tr>
              <th scope="col" className={t.th}>
                Break type
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Transactions
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                Model alone
              </th>
              <th scope="col" className={cx(t.th, t.num)}>
                With rule floors
              </th>
            </tr>
          </thead>
          <tbody>
            {types.map((type) => {
              const alone = recall.model_only[type];
              const floors = recall.with_rule_floors?.[type];
              return (
                <tr key={type}>
                  <td className={t.td}>{breakLabel(type)}</td>
                  <td className={cx(t.td, t.num)}>{formatNumber(alone.n)}</td>
                  <td
                    className={cx(t.td, t.num, alone.recall < 0.9 && "font-semibold text-danger")}
                  >
                    {formatPercent(alone.recall)}
                  </td>
                  <td className={cx(t.td, t.num)}>{formatPercent(floors?.recall)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ScoringRules({ evaluation }: { evaluation: ModelEvaluation }) {
  const floors = Object.entries(evaluation.rule_floors).sort((a, b) => b[1] - a[1]);
  const bands = (evaluation.bands as [number, string][]).filter(([, band]) => isBand(band));
  return (
    <Card title="How scores are set" subtitle="Read from the model's saved configuration">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-medium text-ink-2">Bands</h3>
          <ul className="space-y-1.5 text-sm">
            {bands.map(([min, band]) => (
              <li key={band} className="flex items-center gap-2">
                {isBand(band) && <BandIcon band={band} />}
                <span className="w-20 text-ink">{isBand(band) ? BAND_LABEL[band] : band}</span>
                <span className="text-ink-2">score {min} and up</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-xs font-medium text-ink-2">
            Minimum score when a break is found
          </h3>
          <ul className="space-y-1 text-sm">
            {floors.map(([type, floor]) => (
              <li key={type} className="flex justify-between gap-4">
                <span className="text-ink">{breakLabel(type)}</span>
                <span className="text-ink-2 tabular-nums">{floor}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}

function EvaluationView({ versionId }: { versionId: number }) {
  const query = useModelEvaluation(versionId);
  if (query.isPending) return <Loading label="Loading evaluation" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  const data = query.data;
  const champion = data.champion as unknown as Champion;
  const candidates = data.comparison as unknown as Candidate[];
  const evaluation = data.evaluation as unknown as Evaluation | null;

  return (
    <div className="space-y-5">
      <Headline champion={champion} evaluation={evaluation} />
      <Comparison candidates={candidates} champion={champion} />
      {evaluation ? (
        <>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <ChartCard
              title="Precision and recall"
              subtitle="Model alone, as its threshold moves"
              table={{
                columns: [
                  { key: "threshold", label: "Threshold", numeric: true },
                  { key: "recall", label: "Recall", numeric: true },
                  { key: "precision", label: "Precision", numeric: true },
                ],
                rows: evaluation.pr_curve.map((p) => ({
                  threshold: formatDecimal(p.threshold, 4),
                  recall: formatPercent(p.recall),
                  precision: formatPercent(p.precision),
                })),
              }}
            >
              <CurveChart
                xLabel="Recall"
                yLabel="Precision"
                step
                points={evaluation.pr_curve.map((p) => ({
                  x: p.recall,
                  y: p.precision,
                  details: [{ label: "Threshold", value: formatDecimal(p.threshold, 4) }],
                }))}
                note={
                  evaluation.pr_curve.length < 10
                    ? "Few points: the model's probabilities are almost all near 0 or 1."
                    : undefined
                }
              />
            </ChartCard>
            <ChartCard
              title="ROC curve"
              subtitle="True-positive rate against false-positive rate; the diagonal is chance"
              table={{
                columns: [
                  { key: "threshold", label: "Threshold", numeric: true },
                  { key: "fpr", label: "False-positive rate", numeric: true },
                  { key: "tpr", label: "True-positive rate", numeric: true },
                ],
                rows: evaluation.roc_curve.map((p) => ({
                  threshold: formatDecimal(p.threshold, 4),
                  fpr: formatPercent(p.fpr),
                  tpr: formatPercent(p.tpr),
                })),
              }}
            >
              <CurveChart
                xLabel="False-positive rate"
                yLabel="True-positive rate"
                diagonal
                points={evaluation.roc_curve.map((p) => ({
                  x: p.fpr,
                  y: p.tpr,
                  details: [{ label: "Threshold", value: formatDecimal(p.threshold, 4) }],
                }))}
              />
            </ChartCard>
          </div>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <ChartCard
              title="Calibration"
              subtitle="Predicted probability against the observed break rate; the diagonal is perfect calibration"
              table={{
                columns: [
                  { key: "bin", label: "Probability bin" },
                  { key: "predicted", label: "Mean predicted", numeric: true },
                  { key: "observed", label: "Observed rate", numeric: true },
                  { key: "count", label: "Transactions", numeric: true },
                ],
                rows: evaluation.calibration.map((b) => ({
                  bin: `${formatPercent(b.bin_from)}–${formatPercent(b.bin_to)}`,
                  predicted: formatPercent(b.predicted),
                  observed: formatPercent(b.observed),
                  count: formatNumber(b.count),
                })),
              }}
            >
              <CurveChart
                xLabel="Predicted"
                yLabel="Observed"
                diagonal
                points={evaluation.calibration.map((b) => ({
                  x: b.predicted,
                  y: b.observed,
                  details: [{ label: "Transactions", value: formatNumber(b.count) }],
                }))}
                note={
                  evaluation.calibration.length < 5
                    ? `Only ${evaluation.calibration.length} probability ranges have transactions, so the line between them says little.`
                    : undefined
                }
              />
            </ChartCard>
            <Card
              title="Confusion matrices"
              subtitle={`Test month ${formatPeriod(evaluation.period)}, flagged = high band or above`}
            >
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <ConfusionTable title="Model alone" matrix={evaluation.confusion_model} />
                <ConfusionTable
                  title="With rule floors"
                  matrix={evaluation.confusion_with_rule_floors}
                />
              </div>
            </Card>
          </div>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <ChartCard
              title="What the model relies on"
              subtitle="Mean absolute contribution (log-odds) per feature on the test month"
              table={{
                columns: [
                  { key: "feature", label: "Feature" },
                  { key: "value", label: "Mean |contribution|", numeric: true },
                ],
                rows: evaluation.feature_importance.map((f) => ({
                  feature: f.feature,
                  value: formatDecimal(f.mean_abs_contribution, 3),
                })),
              }}
            >
              <HBarChart
                label="Feature importance"
                labelWidth="12rem"
                format={(v) => v.toFixed(2)}
                bars={evaluation.feature_importance.map((f) => ({
                  key: f.feature,
                  label: f.feature,
                  value: f.mean_abs_contribution,
                }))}
              />
            </ChartCard>
            <RecallByBreak champion={champion} />
          </div>
        </>
      ) : (
        <Alert tone="info">
          This version was saved before evaluation data was recorded. Retrain with{" "}
          <code>fraudml train</code> to see curves and feature importance.
        </Alert>
      )}
      <ScoringRules evaluation={data} />
    </div>
  );
}

export default function ModelsPage() {
  const user = useUser();
  const models = useModels();
  const sync = useSyncModels();
  const [params, setParams] = useSearchParams();

  const versions = models.data ?? [];
  const requested = Number(params.get("version"));
  const selected =
    versions.find((v) => v.id === requested)?.id ??
    versions.find((v) => v.is_active)?.id ??
    versions[0]?.id;

  return (
    <>
      <PageHeader
        title="Models"
        description="How well each saved model finds breaks, and which one is scoring."
        actions={
          can.manageModels(user.role) && (
            <Button
              onClick={() => sync.mutate()}
              busy={sync.isPending}
              title="Register models trained with fraudml train since the API started"
            >
              <Icon name="refresh" size={16} />
              Check for new models
            </Button>
          )
        }
      />
      {sync.isError && (
        <div className="mb-4">
          <Alert>{sync.error.message}</Alert>
        </div>
      )}
      {models.isPending ? (
        <Loading />
      ) : models.isError ? (
        <ErrorState error={models.error} onRetry={() => models.refetch()} />
      ) : versions.length === 0 ? (
        <Card>
          <Empty>
            No models registered. Train one with fraudml train, then check for new models.
          </Empty>
        </Card>
      ) : (
        <div className="space-y-5">
          <VersionsTable
            versions={versions}
            selected={selected}
            onSelect={(id) => setParams({ version: String(id) }, { replace: true })}
          />
          {selected !== undefined ? (
            <EvaluationView versionId={selected} />
          ) : (
            <p className="text-ink-2">{DASH}</p>
          )}
        </div>
      )}
    </>
  );
}
