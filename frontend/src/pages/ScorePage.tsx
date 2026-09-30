import { zodResolver } from "@hookform/resolvers/zod";
import { type FieldErrors, useForm, type UseFormRegister, useWatch } from "react-hook-form";
import { Link } from "react-router";
import type { ScoreResult, SystemCode } from "../api/client";
import { useScoreTransaction } from "../api/queries";
import { FactorBars } from "../components/FactorBars";
import { Icon } from "../components/Icon";
import { RiskGauge } from "../components/RiskGauge";
import { Alert, Button, Card, Field, Input, PageHeader, Select } from "../components/ui";
import { formatDecimal, formatUsd, systemName } from "../lib/format";
import {
  COUNTRIES,
  CURRENCIES,
  EXAMPLES,
  KEY_LABEL,
  type RecordValues,
  SCORE_FORM_DEFAULTS,
  scoreFormSchema,
  type ScoreFormValues,
  SYSTEMS,
  toRequest,
} from "../lib/scoreForm";

function RecordFields({
  system,
  register,
  errors,
}: {
  system: SystemCode;
  register: UseFormRegister<ScoreFormValues>;
  errors: FieldErrors<ScoreFormValues>;
}) {
  const fieldErrors = errors.records?.[system];
  const name = <K extends keyof RecordValues>(key: K) => `records.${system}.${key}` as const;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <Field label={KEY_LABEL[system].label} error={fieldErrors?.account_key?.message}>
        {(props) => (
          <Input
            {...props}
            placeholder={KEY_LABEL[system].placeholder}
            {...register(name("account_key"))}
          />
        )}
      </Field>
      <Field label="Date" error={fieldErrors?.transaction_date?.message}>
        {(props) => <Input {...props} type="date" {...register(name("transaction_date"))} />}
      </Field>
      <Field label="Amount" error={fieldErrors?.amount?.message}>
        {(props) => (
          <Input
            {...props}
            inputMode="decimal"
            placeholder="1250.00"
            {...register(name("amount"))}
          />
        )}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Currency" error={fieldErrors?.currency?.message}>
          {(props) => (
            <Input
              {...props}
              list="currencies"
              className="uppercase"
              {...register(name("currency"))}
            />
          )}
        </Field>
        <Field label="Country" error={fieldErrors?.country?.message}>
          {(props) => (
            <Input
              {...props}
              list="countries"
              className="uppercase"
              {...register(name("country"))}
            />
          )}
        </Field>
      </div>
      <Field
        label="Description"
        className="sm:col-span-2"
        error={fieldErrors?.description?.message}
      >
        {(props) => (
          <Input {...props} placeholder="Vendor payment" {...register(name("description"))} />
        )}
      </Field>
    </div>
  );
}

function Result({ result }: { result: ScoreResult }) {
  const facts = [
    {
      label: "Priority",
      value: String(result.priority),
      hint: "Risk weighted by the money at stake",
    },
    { label: "Exposure", value: formatUsd(result.exposure_usd), hint: "Approximate USD at stake" },
    { label: "Model probability", value: formatDecimal(result.probability, 3) },
    { label: "Model score", value: String(result.model_score) },
  ];
  return (
    <div className="space-y-5">
      <Card
        title={`Transaction ${result.transaction_id}`}
        subtitle={
          result.created
            ? `New transaction, recorded in ${result.in_systems.map(systemName).join(", ")}`
            : `Merged with the stored transaction, now recorded in ${result.in_systems.map(systemName).join(", ")}`
        }
        actions={
          <Link
            to={`/transactions/${encodeURIComponent(result.transaction_id)}`}
            className="inline-flex items-center gap-1 text-xs font-medium text-accent-text hover:underline"
          >
            Open and review
            <Icon name="external" size={14} />
          </Link>
        }
      >
        <RiskGauge score={result.risk_score} />
        <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
          {facts.map((fact) => (
            <div key={fact.label} title={fact.hint}>
              <dt className="text-xs text-ink-2">{fact.label}</dt>
              <dd className="text-base font-semibold text-ink">{fact.value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-ink-2">
          Model {result.model_version}
          {result.latency_ms != null && ` · scored in ${Math.round(result.latency_ms)} ms`}
        </p>
      </Card>

      <Card
        title="Checks that failed"
        subtitle="Deterministic cross-system and business-rule checks"
      >
        {result.rule_hits.length === 0 ? (
          <p className="flex items-center gap-2 text-sm text-ink-2">
            <Icon name="check" size={16} className="text-success" />
            No breaks: the systems agree and every rule passes.
          </p>
        ) : (
          <ul className="space-y-2">
            {result.rule_hits.map((hit, index) => (
              <li key={index} className="flex gap-2 text-sm text-ink">
                <Icon name="alert" size={16} className="mt-0.5 shrink-0 text-danger" />
                {hit.reason}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card
        title="Why the model scored it this way"
        subtitle="Largest contributions to the model's probability"
      >
        <FactorBars factors={result.top_factors} />
      </Card>
    </div>
  );
}

export default function ScorePage() {
  const score = useScoreTransaction();
  const {
    register,
    handleSubmit,
    control,
    reset,
    getValues,
    setValue,
    formState: { errors },
  } = useForm<ScoreFormValues>({
    resolver: zodResolver(scoreFormSchema),
    defaultValues: SCORE_FORM_DEFAULTS,
  });

  const source = useWatch({ control, name: "source_system" });
  const include = useWatch({ control, name: "include" });

  const copyFromSource = (system: SystemCode) => {
    const from = getValues(`records.${source}`);
    setValue(`records.${system}`, {
      ...from,
      account_key: getValues(`records.${system}.account_key`),
    });
  };

  const onSubmit = handleSubmit((values) => score.mutate(toRequest(values)));

  return (
    <>
      <PageHeader
        title="Score a transaction"
        description="Enter one system's record, and the other systems' records if you have them. The score compares them, checks the business rules and runs the model. If the transaction ID is already stored, the new records are merged in."
      />
      <datalist id="currencies">
        {CURRENCIES.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      <datalist id="countries">
        {COUNTRIES.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <form onSubmit={onSubmit} noValidate className="space-y-5">
          <Card
            title="Transaction"
            actions={
              <Select
                aria-label="Fill with an example"
                className="h-8 w-auto text-xs"
                value=""
                onChange={(event) => {
                  const example = EXAMPLES[Number(event.target.value)];
                  if (example) {
                    reset(example.values);
                    score.reset();
                  }
                }}
              >
                <option value="">Try an example…</option>
                {EXAMPLES.map((example, index) => (
                  <option key={example.label} value={index}>
                    {example.label}
                  </option>
                ))}
              </Select>
            }
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field
                label="Transaction ID (optional)"
                hint="Leave blank for a new one. Reuse an ID to add another system's record."
                error={errors.transaction_id?.message}
              >
                {(props) => (
                  <Input
                    {...props}
                    placeholder="9F3A5C7E1B2D4F60"
                    {...register("transaction_id")}
                  />
                )}
              </Field>
              <Field label="Recorded in">
                {(props) => (
                  <Select {...props} {...register("source_system")}>
                    {SYSTEMS.map((system) => (
                      <option key={system} value={system}>
                        {systemName(system)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
          </Card>

          <Card title={`${systemName(source)} record`}>
            <RecordFields system={source} register={register} errors={errors} />
          </Card>

          {SYSTEMS.filter((system) => system !== source).map((system) => (
            <Card
              key={system}
              title={
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-[var(--accent)]"
                    {...register(`include.${system}`)}
                  />
                  Also recorded in {systemName(system)}
                </label>
              }
              actions={
                include[system] ? (
                  <Button size="sm" variant="ghost" onClick={() => copyFromSource(system)}>
                    Copy from {systemName(source)}
                  </Button>
                ) : undefined
              }
              bodyClassName={include[system] ? "p-4" : "hidden"}
            >
              {include[system] && (
                <RecordFields system={system} register={register} errors={errors} />
              )}
            </Card>
          ))}

          {score.isError && <Alert title="Not scored">{score.error.message}</Alert>}
          <div className="flex gap-2">
            <Button type="submit" variant="primary" busy={score.isPending}>
              Score transaction
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                reset(SCORE_FORM_DEFAULTS);
                score.reset();
              }}
            >
              Clear
            </Button>
          </div>
        </form>

        <div aria-live="polite">
          {score.data ? (
            <Result result={score.data} />
          ) : (
            <div className="rounded-lg border border-dashed border-line p-8 text-center text-sm text-ink-2">
              The risk assessment appears here: a 0–100 score and band, the checks that failed, and
              the model's main reasons.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
