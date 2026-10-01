import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { analyst, approver, batch } from "../test/fixtures";
import { renderApp } from "../test/render";
import { mockApi, page } from "../test/server";

const file = (name: string) => new File(["data"], name);

it("checks the form before uploading", async () => {
  const api = mockApi({ "GET /api/v1/ingestion/batches": page([batch()]) }, { user: analyst });
  const user = userEvent.setup();
  renderApp("/ingestion");

  await user.click(await screen.findByRole("button", { name: "Upload and load" }));

  expect(await screen.findByText("Enter the month as YYYYMM, e.g. 202609")).toBeInTheDocument();
  expect(screen.getByText("Choose the GL report file")).toBeInTheDocument();
  expect(screen.getByText("Choose the MA records file")).toBeInTheDocument();
  expect(screen.getByLabelText("Month")).toHaveFocus();
  expect(api.to("POST", "/api/v1/ingestion/upload")).toHaveLength(0);
});

it("uploads a month and shows it queued", async () => {
  const api = mockApi(
    {
      "GET /api/v1/ingestion/batches": page([batch()]),
      "POST /api/v1/ingestion/upload": batch({
        id: 8,
        period: "202609",
        status: "queued",
        records: {},
        summary: {},
      }),
    },
    { user: analyst },
  );
  const user = userEvent.setup();
  renderApp("/ingestion");

  await user.type(await screen.findByLabelText("Month"), "202609");
  await user.upload(screen.getByLabelText("GL report"), file("GL_202609.xml"));
  await user.upload(screen.getByLabelText("FA report"), file("FA_202609.csv"));
  await user.upload(screen.getByLabelText("Join map"), file("join_map.txt"));
  await user.upload(screen.getByLabelText("MA records"), file("ma_server.py"));
  await user.click(screen.getByRole("button", { name: "Upload and load" }));

  expect(await screen.findByText(/Batch 8 for Sep 2026 is queued/)).toBeInTheDocument();
  const [call] = api.to("POST", "/api/v1/ingestion/upload");
  const form = call.body as FormData;
  expect(form.get("period")).toBe("202609");
  expect((form.get("gl") as File).name).toBe("GL_202609.xml");
  expect((form.get("ma") as File).name).toBe("ma_server.py");
  expect(form.has("ma_url")).toBe(false);
  // The history reloads to show the new batch.
  await waitFor(() => expect(api.to("GET", "/api/v1/ingestion/batches").length).toBeGreaterThan(1));
});

it("shows the load history, with failures, to everyone but the form only to makers", async () => {
  mockApi(
    {
      "GET /api/v1/ingestion/batches": page([
        batch({
          id: 9,
          status: "failed",
          error: "The gl file must be one of: .xml",
          summary: {},
          records: {},
        }),
        batch(),
      ]),
    },
    { user: approver },
  );
  renderApp("/ingestion");

  expect(await screen.findByText("The gl file must be one of: .xml")).toBeInTheDocument();
  expect(screen.getByText("Failed")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "2,100 (9.4%)" })).toHaveAttribute(
    "href",
    "/transactions?period=202608&suspicious=true",
  );
  expect(
    screen.getByText("Analysts and admins load data. You can follow the load history below."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Upload and load" })).not.toBeInTheDocument();
});
