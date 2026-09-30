import { describe, expect, it } from "vitest";
import { toUploadForm, UPLOAD_DEFAULTS, type UploadValues, validateUpload } from "./uploadForm";

const file = (name: string, content = "data") => new File([content], name);

const valid: UploadValues = {
  period: "202609",
  gl: file("GL_202609.xml"),
  fa: file("FA_202609.csv"),
  join_map: file("join_map.txt"),
  maSource: "file",
  ma: file("ma_server.py"),
  maUrl: "",
};

describe("validateUpload", () => {
  it("passes a complete month", () => {
    expect(validateUpload(valid)).toEqual({});
  });

  it("asks for everything on an empty form", () => {
    expect(Object.keys(validateUpload(UPLOAD_DEFAULTS)).sort()).toEqual([
      "fa",
      "gl",
      "join_map",
      "ma",
      "period",
    ]);
  });

  it("checks the month and file types", () => {
    const errors = validateUpload({
      ...valid,
      period: "2026-09",
      gl: file("GL.csv"),
      fa: file("FA.csv", ""),
    });
    expect(errors.period).toMatch(/YYYYMM/);
    expect(errors.gl).toBe("Must be .xml");
    expect(errors.fa).toBe("This file is empty");
  });

  it("accepts upper-case extensions", () => {
    expect(validateUpload({ ...valid, gl: file("GL_202609.XML") })).toEqual({});
  });

  it("needs an http(s) URL when MA comes from its API", () => {
    const api = { ...valid, maSource: "url" as const, ma: null };
    expect(validateUpload({ ...api, maUrl: "ftp://ma.example.com" }).maUrl).toBeDefined();
    expect(validateUpload({ ...api, maUrl: "https://ma.example.com/records" })).toEqual({});
  });
});

describe("toUploadForm", () => {
  it("sends either the MA file or its URL", () => {
    const withFile = toUploadForm(valid);
    expect(withFile.get("period")).toBe("202609");
    expect((withFile.get("ma") as File).name).toBe("ma_server.py");
    expect(withFile.has("ma_url")).toBe(false);

    const withUrl = toUploadForm({
      ...valid,
      maSource: "url",
      maUrl: " https://ma.example.com/records ",
    });
    expect(withUrl.get("ma_url")).toBe("https://ma.example.com/records");
    expect(withUrl.has("ma")).toBe(false);
  });
});
