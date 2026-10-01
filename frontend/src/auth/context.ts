import { createContext, useContext } from "react";
import type { Role, User } from "../api/client";

export interface Session {
  token: string;
  user: User;
  /** Epoch milliseconds when the token stops working. */
  expiresAt: number;
}

export interface AuthValue {
  user: User | null;
  /** Why the user was signed out, for the login page ("expired"), if not by choice. */
  signedOutReason: "expired" | null;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

export const AuthContext = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

/** The signed-in user; only call under <RequireAuth>. */
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("useUser called without a signed-in user");
  return user;
}

/** What each role may do. The API enforces the same rules; the UI only hides what would fail. */
export const can = {
  score: (role: Role) => role === "analyst" || role === "admin",
  review: (role: Role) => role === "analyst" || role === "admin",
  approve: (role: Role) => role === "approver" || role === "admin",
  upload: (role: Role) => role === "analyst" || role === "admin",
  manageUsers: (role: Role) => role === "admin",
  manageModels: (role: Role) => role === "admin",
  readAudit: (role: Role) => role === "approver" || role === "admin",
};

export const ROLE_LABEL: Record<Role, string> = {
  analyst: "Analyst",
  approver: "Approver",
  admin: "Admin",
};
