import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { analyst, summary } from "../test/fixtures";
import { renderApp } from "../test/render";
import { mockApi, page, status } from "../test/server";

it("signs in and returns to the page that was asked for", async () => {
  const api = mockApi({
    "POST /api/v1/auth/login": {
      access_token: "fresh-token",
      token_type: "bearer",
      expires_in: 3600,
      user: analyst,
    },
    "GET /api/v1/auth/me": analyst,
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
  const [login] = api.to("POST", "/api/v1/auth/login");
  expect(String(login.body)).toBe("username=analyst%40example.com&password=analyst-password-123");
  await waitFor(() => expect(api.to("GET", "/api/v1/transactions")).not.toHaveLength(0));
  expect(api.to("GET", "/api/v1/transactions")[0].headers.get("Authorization")).toBe(
    "Bearer fresh-token",
  );
});

it("says so when the password is wrong", async () => {
  mockApi({ "POST /api/v1/auth/login": status(401, { detail: "Incorrect email or password" }) });
  const user = userEvent.setup();
  renderApp("/login");

  await user.type(screen.getByLabelText("Email"), "analyst@example.com");
  await user.type(screen.getByLabelText("Password"), "wrong-password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "That email and password don't match an active account.",
  );
});

it("signs out and explains why when the API rejects the token", async () => {
  mockApi(
    {
      "GET /api/v1/analytics/summary": status(401, { detail: "Token expired" }),
      "GET /api/v1/transactions": status(401, { detail: "Token expired" }),
    },
    { user: analyst },
  );
  const app = renderApp("/transactions", { user: analyst });

  expect(
    await screen.findByText("Your session ended. Sign in again to continue."),
  ).toBeInTheDocument();
  expect(app.location().pathname).toBe("/login");
  expect(sessionStorage.length).toBe(0);
});
