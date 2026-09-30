import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { ChartCard } from "./ChartCard";

it("switches between the chart and a table of the same numbers", async () => {
  const user = userEvent.setup();
  render(
    <ChartCard
      title="Risk bands"
      table={{
        columns: [
          { key: "band", label: "Band" },
          { key: "count", label: "Transactions", numeric: true },
        ],
        rows: [
          { band: "High", count: "2,100" },
          { band: "Critical", count: "841" },
        ],
      }}
    >
      <div>the chart</div>
    </ChartCard>,
  );

  expect(screen.getByText("the chart")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Show table" }));

  const table = screen.getByRole("table");
  expect(table).toHaveTextContent("Critical");
  expect(screen.getByRole("columnheader", { name: "Transactions" })).toBeInTheDocument();
  expect(screen.queryByText("the chart")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Show chart" }));
  expect(screen.getByText("the chart")).toBeInTheDocument();
});
