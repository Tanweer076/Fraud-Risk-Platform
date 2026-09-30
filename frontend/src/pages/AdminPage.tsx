import { zodResolver } from "@hookform/resolvers/zod";
import { Fragment, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, useSearchParams } from "react-router";
import type { Role, User } from "../api/client";
import {
  type AuditFilters,
  useAudit,
  useCreateUser,
  useUpdateUser,
  useUsers,
} from "../api/queries";
import { can, ROLE_LABEL, useUser } from "../auth/context";
import { SelectFilter, TextFilter } from "../components/Filters";
import { Icon } from "../components/Icon";
import {
  Alert,
  Button,
  Card,
  Chip,
  Empty,
  ErrorState,
  Field,
  Input,
  Loading,
  PageHeader,
  Pagination,
  Segmented,
  Select,
} from "../components/ui";
import {
  actionLabel,
  AUDIT_ACTIONS,
  AUDIT_ENTITIES,
  auditRecord,
  describeChanges,
  formatAuditValue,
} from "../lib/audit";
import { cx, table as t } from "../lib/cx";
import { DASH, formatDateTime } from "../lib/format";
import {
  MIN_PASSWORD,
  NEW_USER_DEFAULTS,
  newUserSchema,
  type NewUserValues,
  passwordSchema,
  ROLE_HINT,
  ROLES,
} from "../lib/userForm";

const AUDIT_PAGE_SIZE = 50;
const MAX_VALUE_LENGTH = 120;

type Tab = "users" | "audit";

function NewUserForm() {
  const create = useCreateUser();
  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<NewUserValues>({
    resolver: zodResolver(newUserSchema),
    defaultValues: NEW_USER_DEFAULTS,
  });
  const role = useWatch({ control, name: "role" });

  const onSubmit = handleSubmit((values) =>
    create.mutate(values, { onSuccess: () => reset(NEW_USER_DEFAULTS) }),
  );

  return (
    <Card title="Add a user" subtitle="They sign in with this email and password.">
      <form onSubmit={onSubmit} noValidate className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="Email" error={errors.email?.message}>
          {(props) => <Input {...props} type="email" autoComplete="off" {...register("email")} />}
        </Field>
        <Field label="Full name" hint="Optional" error={errors.full_name?.message}>
          {(props) => <Input {...props} autoComplete="off" {...register("full_name")} />}
        </Field>
        <Field label="Role" hint={ROLE_HINT[role]} error={errors.role?.message}>
          {(props) => (
            <Select {...props} {...register("role")}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          label="Password"
          hint={`At least ${MIN_PASSWORD} characters. Give it to them through a secure channel.`}
          error={errors.password?.message}
        >
          {(props) => (
            <Input
              {...props}
              type="password"
              autoComplete="new-password"
              {...register("password")}
            />
          )}
        </Field>
        <div className="space-y-3 md:col-span-2">
          {create.isError && <Alert>{create.error.message}</Alert>}
          {create.isSuccess && (
            <Alert tone="success">
              Added {create.data.email} as {ROLE_LABEL[create.data.role].toLowerCase()}.
            </Alert>
          )}
          <Button type="submit" variant="primary" busy={create.isPending}>
            Add user
          </Button>
        </div>
      </form>
    </Card>
  );
}

function PasswordForm({ user, onDone }: { user: User; onDone: (changed: boolean) => void }) {
  const update = useUpdateUser();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ password: string }>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { password: "" },
  });

  return (
    <form
      noValidate
      onSubmit={handleSubmit(({ password }) =>
        update.mutate({ id: user.id, password }, { onSuccess: () => onDone(true) }),
      )}
      className="flex flex-wrap items-start gap-3"
    >
      <Field
        label={`New password for ${user.email}`}
        error={errors.password?.message}
        className="w-72 max-w-full"
      >
        {(props) => (
          <Input {...props} type="password" autoComplete="new-password" {...register("password")} />
        )}
      </Field>
      <div className="flex gap-2 pt-5">
        <Button type="submit" variant="primary" busy={update.isPending}>
          Set password
        </Button>
        <Button variant="ghost" onClick={() => onDone(false)}>
          Cancel
        </Button>
      </div>
      {update.isError && (
        <div className="basis-full">
          <Alert>{update.error.message}</Alert>
        </div>
      )}
    </form>
  );
}

function UsersTable() {
  const me = useUser();
  const query = useUsers();
  const update = useUpdateUser();
  const [passwordFor, setPasswordFor] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const busy = (id: number) => update.isPending && update.variables?.id === id;

  const change = (user: User, patch: { role?: Role; is_active?: boolean }) => {
    setNotice(null);
    update.mutate({ id: user.id, ...patch });
  };

  return (
    <Card
      title="Users"
      subtitle="Deactivated users can't sign in; their history stays. You can't change your own role or deactivate yourself."
      bodyClassName="p-0"
    >
      {(update.isError || notice) && (
        <div className="px-4 pt-4">
          {update.isError ? (
            <Alert>{update.error.message}</Alert>
          ) : (
            <Alert tone="success">{notice}</Alert>
          )}
        </div>
      )}
      {query.isPending ? (
        <div className="px-4">
          <Loading label="Loading users" />
        </div>
      ) : query.isError ? (
        <div className="p-4">
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        </div>
      ) : (
        <div className={t.wrap}>
          <table className={t.table}>
            <thead>
              <tr>
                <th scope="col" className={t.th}>
                  Name
                </th>
                <th scope="col" className={t.th}>
                  Email
                </th>
                <th scope="col" className={t.th}>
                  Role
                </th>
                <th scope="col" className={t.th}>
                  Status
                </th>
                <th scope="col" className={t.th}>
                  Added
                </th>
                <th scope="col" className={t.th}>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((user) => {
                const self = user.id === me.id;
                return (
                  <Fragment key={user.id}>
                    <tr
                      className={cx(
                        t.row,
                        "*:align-middle",
                        passwordFor === user.id && "bg-subtle",
                      )}
                    >
                      <td className={t.td}>
                        <span className="inline-flex items-center gap-2">
                          {user.full_name || DASH}
                          {self && <Chip>You</Chip>}
                        </span>
                      </td>
                      <td className={t.td}>{user.email}</td>
                      <td className={t.td}>
                        <Select
                          aria-label={`Role for ${user.email}`}
                          className="h-8 w-auto text-xs"
                          value={user.role}
                          disabled={self || busy(user.id)}
                          onChange={(event) => change(user, { role: event.target.value as Role })}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {ROLE_LABEL[r]}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className={cx(t.td, "whitespace-nowrap")}>
                        {user.is_active ? (
                          <span className="inline-flex items-center gap-1.5">
                            <Icon name="check" size={14} className="text-success" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-ink-2">
                            <Icon name="close" size={14} />
                            Deactivated
                          </span>
                        )}
                      </td>
                      <td className={cx(t.td, "whitespace-nowrap")}>
                        {formatDateTime(user.created_at)}
                      </td>
                      <td className={cx(t.td, "text-right whitespace-nowrap")}>
                        <span className="inline-flex gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-expanded={passwordFor === user.id}
                            onClick={() => {
                              setNotice(null);
                              setPasswordFor(passwordFor === user.id ? null : user.id);
                            }}
                          >
                            Set password
                          </Button>
                          {!self && (
                            <Button
                              size="sm"
                              variant={user.is_active ? "danger" : "secondary"}
                              busy={busy(user.id)}
                              onClick={() => change(user, { is_active: !user.is_active })}
                            >
                              {user.is_active ? "Deactivate" : "Reactivate"}
                            </Button>
                          )}
                        </span>
                      </td>
                    </tr>
                    {passwordFor === user.id && (
                      <tr>
                        <td colSpan={6} className="border-b border-line bg-subtle px-3 py-3">
                          <PasswordForm
                            user={user}
                            onDone={(changed) => {
                              setPasswordFor(null);
                              if (changed) setNotice(`Password changed for ${user.email}.`);
                            }}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function clip(text: string) {
  return text.length > MAX_VALUE_LENGTH ? `${text.slice(0, MAX_VALUE_LENGTH)}…` : text;
}

function Changes({
  before,
  after,
}: {
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}) {
  const changes = describeChanges(before, after);
  if (changes.length === 0) return <>{DASH}</>;
  return (
    <ul className="space-y-0.5 text-xs">
      {changes.map((c) => (
        <li key={c.field} className="break-words">
          <span className="font-medium text-ink">{c.field}</span>
          <span className="text-ink-2">: </span>
          {"before" in c && "after" in c ? (
            <>
              <span className="text-ink-2">{clip(formatAuditValue(c.before))}</span>
              <span className="text-ink-2"> → </span>
              <span>{clip(formatAuditValue(c.after))}</span>
            </>
          ) : (
            <span>{clip(formatAuditValue("after" in c ? c.after : c.before))}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function AuditLog() {
  const me = useUser();
  const [params, setParams] = useSearchParams();
  const filters: AuditFilters = {
    entity: params.get("entity") || undefined,
    action: params.get("action") || undefined,
    entity_id: params.get("entity_id") || undefined,
  };
  const page = Math.max(1, Number(params.get("page")) || 1);
  const query = useAudit(filters, page, AUDIT_PAGE_SIZE);
  // Only admins may list users; approvers see user numbers.
  const users = useUsers({ enabled: can.manageUsers(me.role) });
  const emails = new Map((users.data ?? []).map((u) => [u.id, u.email]));
  const active = Object.values(filters).some(Boolean);

  const update = (patch: AuditFilters & { page?: number }) => {
    const next = new URLSearchParams(params);
    for (const key of ["entity", "action", "entity_id"] as const) {
      if (!(key in patch)) continue;
      const value = patch[key];
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (patch.page && patch.page > 1) next.set("page", String(patch.page));
    else next.delete("page");
    setParams(next);
  };

  const who = (userId: number | null) => {
    if (userId == null) return "System";
    if (userId === me.id) return "You";
    return emails.get(userId) ?? `User ${userId}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3" role="group" aria-label="Audit filters">
        <SelectFilter
          label="Record type"
          value={filters.entity ?? ""}
          onChange={(entity) => update({ entity })}
        >
          <option value="">All</option>
          {AUDIT_ENTITIES.map((e) => (
            <option key={e.value} value={e.value}>
              {e.label}
            </option>
          ))}
        </SelectFilter>
        <SelectFilter
          label="Action"
          value={filters.action ?? ""}
          onChange={(action) => update({ action })}
        >
          <option value="">All</option>
          {AUDIT_ACTIONS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </SelectFilter>
        <TextFilter
          label="Record ID"
          value={filters.entity_id}
          placeholder="Transaction ID, review number…"
          onApply={(entity_id) => update({ entity_id })}
          className="w-64"
        />
        {active && (
          <Button
            variant="ghost"
            onClick={() => update({ entity: undefined, action: undefined, entity_id: undefined })}
          >
            Clear filters
          </Button>
        )}
      </div>
      <Card
        title="Audit log"
        subtitle="Newest first. Every change made through the API, with who made it and what changed."
        bodyClassName="p-4"
      >
        {query.isPending ? (
          <Loading label="Loading the audit log" />
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <Empty>
            {active ? "No entries match these filters." : "Nothing has been logged yet."}
          </Empty>
        ) : (
          <>
            <div className={cx(t.wrap, query.isPlaceholderData && "opacity-60")}>
              <table className={t.table}>
                <thead>
                  <tr>
                    <th scope="col" className={t.th}>
                      When
                    </th>
                    <th scope="col" className={t.th}>
                      Who
                    </th>
                    <th scope="col" className={t.th}>
                      Action
                    </th>
                    <th scope="col" className={t.th}>
                      Record
                    </th>
                    <th scope="col" className={t.th}>
                      Changes
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((entry) => {
                    const record = auditRecord(entry.entity, entry.entity_id);
                    return (
                      <tr key={entry.id} className={cx(t.row, "align-top")}>
                        <td className={cx(t.td, "whitespace-nowrap")}>
                          {formatDateTime(entry.created_at)}
                        </td>
                        <td className={t.td}>{who(entry.user_id)}</td>
                        <td className={cx(t.td, "whitespace-nowrap")}>
                          {actionLabel(entry.action)}
                        </td>
                        <td className={cx(t.td, "whitespace-nowrap")}>
                          {record.href ? (
                            <Link
                              to={record.href}
                              className="font-medium text-accent-text hover:underline"
                            >
                              {record.label}
                            </Link>
                          ) : (
                            record.label
                          )}
                        </td>
                        <td className={cx(t.td, "min-w-64")}>
                          <Changes before={entry.before} after={entry.after} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pageSize={AUDIT_PAGE_SIZE}
              total={query.data.total}
              onPage={(p) => update({ page: p })}
            />
          </>
        )}
      </Card>
    </div>
  );
}

export default function AdminPage() {
  const user = useUser();
  const [params, setParams] = useSearchParams();
  const tabs: { value: Tab; label: string }[] = [
    ...(can.manageUsers(user.role) ? [{ value: "users" as const, label: "Users" }] : []),
    ...(can.readAudit(user.role) ? [{ value: "audit" as const, label: "Audit log" }] : []),
  ];
  const tab = tabs.find((item) => item.value === params.get("tab"))?.value ?? tabs[0]?.value;

  return (
    <>
      <PageHeader
        title="Admin"
        description={
          can.manageUsers(user.role)
            ? "Manage who can sign in and what they may do, and read the audit trail."
            : "The audit trail: every change made through the API, with who made it and what changed."
        }
      />
      {tabs.length > 1 && (
        <div className="mb-4">
          <Segmented
            label="Admin section"
            value={tab}
            options={tabs}
            onChange={(value) => setParams({ tab: value })}
          />
        </div>
      )}
      {tab === "users" ? (
        <div className="space-y-5">
          <NewUserForm />
          <UsersTable />
        </div>
      ) : tab === "audit" ? (
        <AuditLog />
      ) : (
        <Alert>You don't have access to this page.</Alert>
      )}
    </>
  );
}
