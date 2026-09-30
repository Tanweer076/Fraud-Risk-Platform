import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  apiFetch,
  setAuthToken,
  setUnauthorizedHandler,
  type Token,
  unwrap,
} from "../api/client";
import { AuthContext, type AuthValue, type Session } from "./context";
import { clearSession, loadSession, saveSession } from "./storage";

// Longest timer browsers allow; tokens are much shorter-lived, this only guards the arithmetic.
const MAX_TIMEOUT = 2 ** 31 - 1;

function restore(): Session | null {
  const session = loadSession();
  // Set synchronously so the first queries of the restored session already carry the token.
  setAuthToken(session?.token ?? null);
  return session;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(restore);
  const [signedOutReason, setSignedOutReason] = useState<"expired" | null>(null);

  const end = useCallback(
    (reason: "expired" | null) => {
      clearSession();
      setAuthToken(null);
      setSession(null);
      setSignedOutReason(reason);
      queryClient.clear();
    },
    [queryClient],
  );
  const logout = useCallback(() => end(null), [end]);

  useEffect(() => {
    setUnauthorizedHandler(() => end("expired"));
    return () => setUnauthorizedHandler(null);
  }, [end]);

  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(
      () => end("expired"),
      Math.min(session.expiresAt - Date.now(), MAX_TIMEOUT),
    );
    return () => clearTimeout(timer);
  }, [session, end]);

  // Refresh the user on load, so a role change by an admin shows without signing in again.
  const me = useQuery({
    queryKey: ["me", session?.token],
    queryFn: () => unwrap(api.GET("/api/v1/auth/me")),
    enabled: session !== null,
    staleTime: 5 * 60_000,
  });

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    });
    const token = (await response.json()) as Token;
    const next: Session = {
      token: token.access_token,
      user: token.user,
      expiresAt: Date.now() + token.expires_in * 1000,
    };
    saveSession(next);
    setAuthToken(next.token);
    setSession(next);
    setSignedOutReason(null);
    return next.user;
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      user: session ? (me.data ?? session.user) : null,
      signedOutReason,
      login,
      logout,
    }),
    [session, me.data, signedOutReason, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
