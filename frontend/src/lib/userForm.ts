/** The admin's new-user and set-password forms, with the API's own limits. */
import { z } from "zod";
import type { Role } from "../api/client";

export const ROLES: Role[] = ["analyst", "approver", "admin"];

export const ROLE_HINT: Record<Role, string> = {
  analyst: "Scores transactions, loads data and records findings",
  approver: "Approves or rejects findings and reads the audit log",
  admin: "Everything, plus users and models",
};

export const MIN_PASSWORD = 12;

const password = z.string().min(MIN_PASSWORD, `Use at least ${MIN_PASSWORD} characters`);

export const newUserSchema = z.object({
  email: z.string().trim().pipe(z.email("Enter a valid email address")),
  full_name: z.string().trim().max(120, "Keep the name under 120 characters"),
  role: z.enum(["analyst", "approver", "admin"]),
  password,
});

export type NewUserValues = z.infer<typeof newUserSchema>;

export const NEW_USER_DEFAULTS: NewUserValues = {
  email: "",
  full_name: "",
  role: "analyst",
  password: "",
};

export const passwordSchema = z.object({ password });
