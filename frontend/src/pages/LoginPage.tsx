import { type FormEvent, useState } from "react";
import { Navigate, useSearchParams } from "react-router";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/context";
import { Alert, Button, Field, Input } from "../components/ui";

/** Only same-app paths are followed after sign-in, never another site. */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function LoginPage() {
  const { user, login, signedOutReason } = useAuth();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={safeNext(params.get("next"))} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "That email and password don't match an active account."
          : err instanceof Error
            ? err.message
            : "Sign-in failed.",
      );
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <div>
            <h1 className="text-lg font-semibold text-ink">Fraud Risk Platform</h1>
            <p className="text-xs text-ink-2">Cross-system transaction risk scoring</p>
          </div>
        </div>
        <form
          onSubmit={submit}
          className="space-y-4 rounded-lg border border-line bg-surface p-5"
          noValidate
        >
          <h2 className="text-base font-semibold text-ink">Sign in</h2>
          {signedOutReason === "expired" && !error && (
            <Alert tone="info">Your session ended. Sign in again to continue.</Alert>
          )}
          {error && <Alert>{error}</Alert>}
          <Field label="Email">
            {(props) => (
              <Input
                {...props}
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            )}
          </Field>
          <Field label="Password">
            {(props) => (
              <Input
                {...props}
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          <Button
            type="submit"
            variant="primary"
            className="w-full"
            busy={busy}
            disabled={!email || !password}
          >
            Sign in
          </Button>
        </form>
        <p className="mt-4 text-xs text-ink-2">
          Accounts are created by an admin (<code>fraudapi create-user</code> on the server).
        </p>
      </div>
    </main>
  );
}
