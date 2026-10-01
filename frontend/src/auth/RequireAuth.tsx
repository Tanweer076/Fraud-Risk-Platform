import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import type { Role } from "../api/client";
import { Alert } from "../components/ui";
import { useAuth } from "./context";

/** Sends signed-out visitors to the login page, then back here. `roles` limits who may see it. */
export function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) {
    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <Alert title="You don't have access to this page">
        It needs the {roles.join(" or ")} role. Ask an admin if you need it.
      </Alert>
    );
  }
  return <>{children}</>;
}
