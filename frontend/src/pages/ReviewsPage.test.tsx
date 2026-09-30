import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { analyst, approver, review, transaction } from "../test/fixtures";
import { renderApp } from "../test/render";
import { mockApi, page } from "../test/server";

it("lets an approver bulk-approve other people's findings but never their own", async () => {
  const own = review({
    id: 12,
    transaction_id: "OWN0000000000012",
    analyst_id: approver.id,
    analyst_email: approver.email,
  });
  const api = mockApi(
    {
      "GET /api/v1/reviews": page([review(), own]),
      "POST /api/v1/reviews/bulk-approve": { approved: [11], skipped: [] },
    },
    { user: approver },
  );
  const user = userEvent.setup();
  renderApp("/reviews?tab=pending", { user: approver });

  const mine = await screen.findByRole("checkbox", { name: "Select review 12" });
  expect(mine).toBeDisabled();
  expect(within(mine.closest("tr")!).getByText("Your finding")).toBeInTheDocument();

  await user.click(screen.getByRole("checkbox", { name: "Select all you can approve" }));
  expect(screen.getByRole("checkbox", { name: "Select review 11" })).toBeChecked();
  expect(mine).not.toBeChecked();

  await user.click(screen.getByRole("button", { name: "Approve 1 selected" }));
  await waitFor(() => expect(api.to("POST", "/api/v1/reviews/bulk-approve")).toHaveLength(1));
  expect(api.to("POST", "/api/v1/reviews/bulk-approve")[0].body).toEqual({ review_ids: [11] });
  expect(await screen.findByText("Approved 1")).toBeInTheDocument();
});

it("lets an analyst record a finding from the queue", async () => {
  const api = mockApi(
    {
      "GET /api/v1/reviews/queue": page([transaction()]),
      "POST /api/v1/reviews": review(),
    },
    { user: analyst },
  );
  const user = userEvent.setup();
  renderApp("/reviews", { user: analyst });

  await user.click(await screen.findByRole("button", { name: "Review" }));
  await user.click(screen.getByRole("radio", { name: "Confirmed break" }));
  await user.type(screen.getByLabelText("Note (optional)"), "FA keyed the wrong amount");
  await user.click(screen.getByRole("button", { name: "Submit for approval" }));

  await waitFor(() => expect(api.to("POST", "/api/v1/reviews")).toHaveLength(1));
  expect(api.to("POST", "/api/v1/reviews")[0].body).toEqual({
    transaction_id: "7C1D2E3F4A5B6C7D",
    decision: "confirmed",
    note: "FA keyed the wrong amount",
  });
});

it("shows approvers the queue without the review button", async () => {
  mockApi({ "GET /api/v1/reviews/queue": page([transaction()]) }, { user: approver });
  renderApp("/reviews", { user: approver });
  expect(await screen.findByRole("link", { name: "7C1D2E3F4A5B6C7D" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Review" })).not.toBeInTheDocument();
});
