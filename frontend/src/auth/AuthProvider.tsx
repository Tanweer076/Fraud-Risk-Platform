import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiFetch, type SessionOut, setUnauthorizedHandler } from "../api/client";
import { Loading } from "../components/ui";
import { AuthContext, type AuthValue, type Session } from "./context";

const SESSION = "/api/v1/auth/session";
const SESSION_KEY = ["session"] as const;

// Longest timer browsers allow; sessions are much shorter-lived, this only guards the arithmetic.
const MAX_TIMEOUT = 2 ** 31 - 1;

function toSession(body: SessionOut): Session {
  return { user: body.user, expiresAt: Date.parse(body.expires_at) };
}

/** The signed-in session from the cookie, or null when there is none (or it has ended). */
async function fetchSession(): Promise<Session | null> {
  try {
    const response = await apiFetch(SESSION);
    return toSession((await response.json()) as SessionOut);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [signedOutReason, setSignedOutReason] = useState<"expired" | null>(null);

  // Asking the API is the only way to know: the cookie is HttpOnly. Refetching now and then also
  // shows a role change by an admin without signing in again.
  const query = useQuery({
    queryKey: SESSION_KEY,
    queryFn: fetchSession,
    staleTime: 5 * 60_000,
    retry: false,
  });
  const session = query.data ?? null;

  const end = useCallback(
    (reason: "expired" | null) => {
      void queryClient.cancelQueries();
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== SESSION_KEY[0] });
      queryClient.setQueryData(SESSION_KEY, null);
      setSignedOutReason(reason);
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await apiFetch(SESSION, { method: "DELETE" });
    } catch {
      // Signed out here either way; the cookie ends with the session.
    }
    end(null);
  }, [end]);

  useEffect(() => {
    if (!session) return;
    setUnauthorizedHandler(() => end("expired"));
    return () => setUnauthorizedHandler(null);
  }, [session, end]);

  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(
      () => end("expired"),
      Math.min(session.expiresAt - Date.now(), MAX_TIMEOUT),
    );
    return () => clearTimeout(timer);
  }, [session, end]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await apiFetch(SESSION, {
        method: "POST",
        body: new URLSearchParams({ username: email, password }),
      });
      const next = toSession((await response.json()) as SessionOut);
      queryClient.setQueryData(SESSION_KEY, next);
      setSignedOutReason(null);
      return next.user;
    },
    [queryClient],
  );

  const value = useMemo<AuthValue>(
    () => ({ user: session?.user ?? null, signedOutReason, login, logout }),
    [session, signedOutReason, login, logout],
  );

  if (query.isPending) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <Loading />
      </main>
    );
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
