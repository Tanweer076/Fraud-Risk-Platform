import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { analyst, approver, scoreResult } from "../test/fixtures";
import { renderApp } from "../test/render";
import { mockApi } from "../test/server";

it("scores an example and shows the risk, the failed checks and the reasons", async () => {
  const api = mockApi({ "POST /api/v1/predictions": scoreResult }, { user: analyst });
  const user = userEvent.setup();
  renderApp("/score");

  await user.selectOptions(
    await screen.findByLabelText("Fill with an example"),
    "FA amount differs",
  );
  await user.click(screen.getByRole("button", { name: "Score transaction" }));

  const meter = await screen.findByRole("meter");
  expect(meter).toHaveAttribute("aria-valuetext", "70 out of 100, High risk");
  expect(screen.getByText("FA amount 4,820.00 differs from GL 48,200.00")).toBeInTheDocument();
  expect(screen.getByText("Amounts differ across systems")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Open and review/ })).toHaveAttribute(
    "href",
    "/transactions/SCORED0000000001",
  );

  const [call] = api.to("POST", "/api/v1/predictions");
  expect(call.body).toMatchObject({
    source_system: "gl",
    account_key: "ACC0001",
    amount: 48200,
    counterparts: {
      ma: { account_key: "CUS-000001", amount: 48200 },
      fa: { account_key: "FA-000001", amount: 4820 },
    },
  });
});

it("shows what is missing instead of sending an incomplete record", async () => {
  const api = mockApi({}, { user: analyst });
  const user = userEvent.setup();
  renderApp("/score");

  await user.click(await screen.findByRole("button", { name: "Score transaction" }));

  const record = screen.getByRole("heading", { name: "GL record" }).closest("section")!;
  expect(await within(record).findByText("Enter the key")).toBeInTheDocument();
  expect(within(record).getByText("Enter a date")).toBeInTheDocument();
  expect(within(record).getByText("Enter an amount")).toBeInTheDocument();
  expect(api.to("POST", "/api/v1/predictions")).toHaveLength(0);
});

it("is not offered to approvers", async () => {
  mockApi({}, { user: approver });
  renderApp("/score");
  expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Score transaction" })).not.toBeInTheDocument();
});
