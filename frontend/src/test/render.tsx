/** Render the real app (routes, auth, React Query) at a URL, optionally signed in. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation, type Location } from "react-router";
import type { User } from "../api/client";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthProvider";
import { saveSession } from "../auth/storage";

export const TEST_TOKEN = "test-token";

export function signIn(user: User) {
  saveSession({ token: TEST_TOKEN, user, expiresAt: Date.now() + 60 * 60 * 1000 });
}

function testQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

export function renderWithClient(ui: ReactNode) {
  const client = testQueryClient();
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

export function renderApp(path: string, { user }: { user?: User } = {}) {
  if (user) signIn(user);
  const current: { location: Location | null } = { location: null };
  function LocationProbe() {
    current.location = useLocation();
    return null;
  }
  const utils = render(
    <QueryClientProvider client={testQueryClient()}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
          <LocationProbe />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
  return {
    ...utils,
    /** The app's current location (path and search), after any navigation. */
    location: () => current.location!,
  };
}
