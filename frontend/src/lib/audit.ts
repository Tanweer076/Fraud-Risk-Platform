/** Labels for the audit trail and a readable list of what each entry changed. */

export const AUDIT_ENTITIES: { value: string; label: string }[] = [
  { value: "transaction", label: "Transactions" },
  { value: "review", label: "Reviews" },
  { value: "ingestion_batch", label: "Ingestion batches" },
  { value: "model_version", label: "Models" },
  { value: "user", label: "Users" },
];

/** Every action the API records, in the order a transaction meets them. */
export const AUDIT_ACTIONS: { value: string; label: string }[] = [
  { value: "ingestion.create", label: "Started a load" },
  { value: "prediction.create", label: "Scored a transaction" },
  { value: "review.create", label: "Recorded a finding" },
  { value: "review.approve", label: "Approved a finding" },
  { value: "review.reject", label: "Rejected a finding" },
  { value: "model.register", label: "Registered models" },
  { value: "model.activate", label: "Activated a model" },
  { value: "user.create", label: "Created a user" },
  { value: "user.update", label: "Updated a user" },
];

const ACTION_LABELS = new Map(AUDIT_ACTIONS.map((a) => [a.value, a.label]));
const ENTITY_LABELS = new Map(AUDIT_ENTITIES.map((e) => [e.value, e.label]));

export function actionLabel(action: string): string {
  return ACTION_LABELS.get(action) ?? action;
}

export function entityLabel(entity: string): string {
  return ENTITY_LABELS.get(entity) ?? entity;
}

export interface Change {
  field: string;
  before?: unknown;
  after?: unknown;
}

type Snapshot = Record<string, unknown> | null | undefined;

/**
 * What an entry changed. With both snapshots, only the fields that differ; with one, all of
 * its fields (a creation records only `after`).
 */
export function describeChanges(before: Snapshot, after: Snapshot): Change[] {
  const b = before ?? {};
  const a = after ?? {};
  const fields = [...new Set([...Object.keys(b), ...Object.keys(a)])];
  const both = before != null && after != null;
  return fields
    .filter((field) => !both || JSON.stringify(b[field]) !== JSON.stringify(a[field]))
    .map((field) => ({
      field,
      ...(field in b ? { before: b[field] } : {}),
      ...(field in a ? { after: a[field] } : {}),
    }));
}

export function formatAuditValue(value: unknown): string {
  if (value === null) return "none";
  if (value === undefined) return "";
  if (typeof value === "string") return value || '""';
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value) && value.every((item) => typeof item !== "object"))
    return value.join(", ");
  return JSON.stringify(value);
}

/** The record an entry is about, with a link to where it is shown when there is one. */
export function auditRecord(
  entity: string,
  entityId: string | null,
): { label: string; href?: string } {
  if (entityId == null) return { label: entityLabel(entity) };
  const id = encodeURIComponent(entityId);
  switch (entity) {
    case "transaction":
      return { label: entityId, href: `/transactions/${id}` };
    case "review":
      return { label: `Review ${entityId}` };
    case "ingestion_batch":
      return { label: `Batch ${entityId}`, href: "/ingestion" };
    case "model_version":
      return { label: `Model version ${entityId}`, href: `/models?version=${id}` };
    case "user":
      return { label: `User ${entityId}` };
    default:
      return { label: `${entity} ${entityId}` };
  }
}
