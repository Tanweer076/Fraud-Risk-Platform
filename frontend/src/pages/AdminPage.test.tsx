import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { admin, analyst, approver } from "../test/fixtures";
import { renderApp } from "../test/render";
import { mockApi, page } from "../test/server";

it("lets an admin change other users but not lock themselves out", async () => {
  const api = mockApi(
    {
      "GET /api/v1/users": [admin, analyst],
      "PATCH /api/v1/users/2": { ...analyst, role: "approver" },
    },
    { user: admin },
  );
  const user = userEvent.setup();
  renderApp("/admin", { user: admin });

  const own = await screen.findByLabelText("Role for admin@example.com");
  expect(own).toBeDisabled();
  expect(
    within(own.closest("tr")!).queryByRole("button", { name: "Deactivate" }),
  ).not.toBeInTheDocument();

  await user.selectOptions(screen.getByLabelText("Role for analyst@example.com"), "approver");
  await waitFor(() => expect(api.to("PATCH", "/api/v1/users/2")).toHaveLength(1));
  expect(api.to("PATCH", "/api/v1/users/2")[0].body).toEqual({ role: "approver" });
});

it("checks a new user's details before creating them", async () => {
  const api = mockApi({ "GET /api/v1/users": [admin] }, { user: admin });
  const user = userEvent.setup();
  renderApp("/admin", { user: admin });

  await user.type(await screen.findByLabelText("Email"), "not-an-email");
  await user.type(screen.getByLabelText("Password"), "short");
  await user.click(screen.getByRole("button", { name: "Add user" }));

  expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
  expect(screen.getByText("Use at least 12 characters")).toBeInTheDocument();
  expect(api.to("POST", "/api/v1/users")).toHaveLength(0);
});

it("shows approvers only the audit log, with filters in the URL", async () => {
  const api = mockApi(
    {
      "GET /api/v1/audit": page([
        {
          id: 40,
          user_id: 2,
          action: "review.create",
          entity: "review",
          entity_id: "11",
          before: null,
          after: { transaction_id: "7C1D2E3F4A5B6C7D", decision: "confirmed", note: "" },
          request_id: "req-1",
          created_at: "2026-09-30T20:05:00Z",
        },
      ]),
    },
    { user: approver },
  );
  const user = userEvent.setup();
  const app = renderApp("/admin", { user: approver });

  const action = await screen.findByRole("cell", { name: "Recorded a finding" });
  const row = within(action.closest("tr")!);
  expect(row.getByRole("cell", { name: "User 2" })).toBeInTheDocument();
  expect(row.getByText("Review 11")).toBeInTheDocument();
  expect(row.getByText("confirmed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Users" })).not.toBeInTheDocument();
  expect(api.to("GET", "/api/v1/users")).toHaveLength(0);

  await user.selectOptions(screen.getByLabelText("Action"), "review.approve");
  expect(new URLSearchParams(app.location().search).get("action")).toBe("review.approve");
  await waitFor(() =>
    expect(api.to("GET", "/api/v1/audit").at(-1)!.query.get("action")).toBe("review.approve"),
  );
});
