/** Render the real app (routes, auth, React Query) at a URL. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation, type Location } from "react-router";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthProvider";

function testQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

export function renderWithClient(ui: ReactNode) {
  const client = testQueryClient();
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

/** Render the whole app at `path`. Who is signed in comes from mockApi's `user`. */
export function renderApp(path: string) {
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
