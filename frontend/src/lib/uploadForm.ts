/** The month-upload form: what the API accepts, checked before sending so mistakes show inline. */

export const PERIOD_PATTERN = /^\d{4}(0[1-9]|1[0-2])$/;

export type UploadFileField = "gl" | "fa" | "join_map" | "ma";

/** File types per source, matching the backend's SUFFIXES. */
export const ACCEPT: Record<UploadFileField, string[]> = {
  gl: [".xml"],
  fa: [".csv"],
  join_map: [".txt", ".csv"],
  ma: [".py", ".csv", ".json"],
};

export const FILE_LABEL: Record<UploadFileField, string> = {
  gl: "GL report",
  fa: "FA report",
  join_map: "Join map",
  ma: "MA records",
};

export interface UploadValues {
  period: string;
  gl: File | null;
  fa: File | null;
  join_map: File | null;
  /** MA comes as a file or from its REST API. */
  maSource: "file" | "url";
  ma: File | null;
  maUrl: string;
}

export type UploadErrors = Partial<Record<"period" | UploadFileField | "maUrl", string>>;

export const UPLOAD_DEFAULTS: UploadValues = {
  period: "",
  gl: null,
  fa: null,
  join_map: null,
  maSource: "file",
  ma: null,
  maUrl: "",
};

function suffix(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

function checkFile(field: UploadFileField, file: File | null): string | undefined {
  if (!file) return `Choose the ${FILE_LABEL[field]} file`;
  if (!ACCEPT[field].includes(suffix(file.name))) return `Must be ${ACCEPT[field].join(" or ")}`;
  if (file.size === 0) return "This file is empty";
  return undefined;
}

function isHttpUrl(text: string): boolean {
  try {
    const url = new URL(text);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function validateUpload(values: UploadValues): UploadErrors {
  const errors: UploadErrors = {};
  if (!PERIOD_PATTERN.test(values.period.trim()))
    errors.period = "Enter the month as YYYYMM, e.g. 202609";
  for (const field of ["gl", "fa", "join_map"] as const) {
    const error = checkFile(field, values[field]);
    if (error) errors[field] = error;
  }
  if (values.maSource === "file") {
    const error = checkFile("ma", values.ma);
    if (error) errors.ma = error;
  } else if (!isHttpUrl(values.maUrl.trim())) {
    errors.maUrl = "Enter an http or https URL";
  }
  return errors;
}

/** The multipart body for POST /ingestion/upload. Call only after validateUpload passes. */
export function toUploadForm(values: UploadValues): FormData {
  const form = new FormData();
  form.set("period", values.period.trim());
  form.set("gl", values.gl!);
  form.set("fa", values.fa!);
  form.set("join_map", values.join_map!);
  if (values.maSource === "file") form.set("ma", values.ma!);
  else form.set("ma_url", values.maUrl.trim());
  return form;
}
