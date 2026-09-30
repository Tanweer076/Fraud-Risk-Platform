import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { analyst, summary, transaction } from "../test/fixtures";
import { renderApp } from "../test/render";
import { mockApi, page } from "../test/server";

it("keeps filters in the URL and sends them to the API", async () => {
  const api = mockApi(
    {
      "GET /api/v1/analytics/summary": summary,
      "GET /api/v1/transactions": page([transaction()], { total: 1 }),
    },
    { user: analyst },
  );
  const user = userEvent.setup();
  const app = renderApp("/transactions?page=3", { user: analyst });

  const row = await screen.findByRole("link", { name: "7C1D2E3F4A5B6C7D" });
  expect(within(row.closest("tr")!).getByText("Amount mismatch")).toBeInTheDocument();

  await user.selectOptions(screen.getByLabelText("Break type"), "amount_mismatch");
  await user.click(screen.getByRole("button", { name: "Critical" }));

  const params = new URLSearchParams(app.location().search);
  expect(params.get("break_type")).toBe("amount_mismatch");
  expect(params.getAll("band")).toEqual(["critical"]);
  expect(params.has("page")).toBe(false); // a new filter starts from the first page
  expect(screen.getByRole("button", { name: "Critical" })).toHaveAttribute("aria-pressed", "true");

  await waitFor(() => {
    const last = api.to("GET", "/api/v1/transactions").at(-1)!;
    expect(last.query.get("break_type")).toBe("amount_mismatch");
    expect(last.query.getAll("band")).toEqual(["critical"]);
    expect(last.query.get("page")).toBe("1");
  });
});

it("reads filters from a shared link", async () => {
  const api = mockApi(
    { "GET /api/v1/analytics/summary": summary, "GET /api/v1/transactions": page([]) },
    { user: analyst },
  );
  renderApp("/transactions?period=202608&suspicious=true&reviewed=false", { user: analyst });

  expect(await screen.findByText("No transactions match these filters.")).toBeInTheDocument();
  expect(screen.getByLabelText("Breaks")).toHaveValue("true");
  const [call] = api.to("GET", "/api/v1/transactions");
  expect(Object.fromEntries(call.query)).toMatchObject({
    period: "202608",
    suspicious: "true",
    reviewed: "false",
  });
});
