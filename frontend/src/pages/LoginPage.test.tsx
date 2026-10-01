import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { analyst, summary } from "../test/fixtures";
import { renderApp } from "../test/render";
import { mockApi, page, sessionFor, status } from "../test/server";

it("signs in and returns to the page that was asked for", async () => {
  const api = mockApi({
    "POST /api/v1/auth/session": sessionFor(analyst),
    "GET /api/v1/analytics/summary": summary,
    "GET /api/v1/transactions": page([]),
  });
  const user = userEvent.setup();
  const app = renderApp("/transactions?period=202608");

  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  await user.type(screen.getByLabelText("Email"), "analyst@example.com");
  await user.type(screen.getByLabelText("Password"), "analyst-password-123");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("heading", { name: "Transactions" })).toBeInTheDocument();
  expect(app.location().search).toBe("?period=202608");
  const [login] = api.to("POST", "/api/v1/auth/session");
  expect(String(login.body)).toBe("username=analyst%40example.com&password=analyst-password-123");
  await waitFor(() => expect(api.to("GET", "/api/v1/transactions")).not.toHaveLength(0));

  // The session is an HttpOnly cookie: no token is handled or kept by the page.
  const [list] = api.to("GET", "/api/v1/transactions");
  expect(list.headers.get("Authorization")).toBeNull();
  expect(list.headers.get("X-Requested-With")).toBe("fetch");
  expect(login.headers.get("X-Requested-With")).toBe("fetch");
  expect(sessionStorage.length + localStorage.length).toBe(0);
});

it("says so when the password is wrong", async () => {
  mockApi({ "POST /api/v1/auth/session": status(401, { detail: "Incorrect email or password" }) });
  const user = userEvent.setup();
  renderApp("/login");

  await user.type(await screen.findByLabelText("Email"), "analyst@example.com");
  await user.type(screen.getByLabelText("Password"), "wrong-password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "That email and password don't match an active account.",
  );
});

it("says so when there are too many attempts", async () => {
  mockApi({
    "POST /api/v1/auth/session": status(429, {
      detail: "Too many requests. Try again in 42 seconds.",
    }),
  });
  const user = userEvent.setup();
  renderApp("/login");

  await user.type(await screen.findByLabelText("Email"), "analyst@example.com");
  await user.type(screen.getByLabelText("Password"), "analyst-password-123");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Too many requests. Try again in 42 seconds.",
  );
});

it("picks up a session that is still open, for example after a reload", async () => {
  mockApi(
    { "GET /api/v1/analytics/summary": summary, "GET /api/v1/transactions": page([]) },
    { user: analyst },
  );
  renderApp("/transactions");

  expect(await screen.findByRole("heading", { name: "Transactions" })).toBeInTheDocument();
});

it("signs out and explains why when the API turns the session down", async () => {
  mockApi(
    {
      "GET /api/v1/analytics/summary": status(401, { detail: "Invalid or expired token" }),
      "GET /api/v1/transactions": status(401, { detail: "Invalid or expired token" }),
    },
    { user: analyst },
  );
  const app = renderApp("/transactions");

  expect(
    await screen.findByText("Your session ended. Sign in again to continue."),
  ).toBeInTheDocument();
  expect(app.location().pathname).toBe("/login");
});

it("signing out asks the API to drop the cookie", async () => {
  const api = mockApi(
    {
      "GET /api/v1/analytics/summary": summary,
      "GET /api/v1/transactions": page([]),
      "DELETE /api/v1/auth/session": status(204),
    },
    { user: analyst },
  );
  const user = userEvent.setup();
  const app = renderApp("/transactions");

  await user.click(await screen.findByRole("button", { name: "Sign out" }));

  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(app.location().pathname).toBe("/login");
  const [signOut] = api.to("DELETE", "/api/v1/auth/session");
  expect(signOut.headers.get("X-Requested-With")).toBe("fetch");
  expect(screen.queryByText("Your session ended. Sign in again to continue.")).toBeNull();
});
