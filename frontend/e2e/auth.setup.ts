import { randomBytes } from "node:crypto";
import { type APIRequestContext, test as setup, expect, request } from "@playwright/test";
import { ADMIN, CSRF, type Role, stateFile, TEST_USERS } from "./support";

async function startSession(api: APIRequestContext, email: string, password: string) {
  const response = await api.post("/api/v1/auth/session", {
    form: { username: email, password },
    headers: CSRF,
  });
  expect(response.status(), `signing in as ${email}: ${await response.text()}`).toBe(200);
}

setup("add the test users and sign everyone in", async ({ baseURL }) => {
  expect(ADMIN.password, "set ADMIN_PASSWORD, as in .env").not.toBe("");

  // The admin signs in with a cookie, like the dashboard, and adds the other two users.
  const admin = await request.newContext({ baseURL });
  await startSession(admin, ADMIN.email, ADMIN.password);
  const passwords = {} as Record<Exclude<Role, "admin">, string>;
  const existing = await admin.get("/api/v1/users");
  expect(existing.ok()).toBe(true);
  const users: { id: number; email: string }[] = await existing.json();

  for (const role of ["analyst", "approver"] as const) {
    // A fresh password on every run, so these users never have one anybody knows.
    const password = randomBytes(18).toString("base64url");
    passwords[role] = password;
    const known = users.find((user) => user.email === TEST_USERS[role].email);
    const response = known
      ? await admin.patch(`/api/v1/users/${known.id}`, {
          headers: CSRF,
          data: { password, role, is_active: true },
        })
      : await admin.post("/api/v1/users", {
          headers: CSRF,
          data: { ...TEST_USERS[role], password, role },
        });
    expect(response.ok(), `saving the ${role}: ${await response.text()}`).toBe(true);
  }
  await admin.storageState({ path: stateFile("admin") });
  await admin.dispose();

  for (const role of ["analyst", "approver"] as const) {
    const api = await request.newContext({ baseURL });
    await startSession(api, TEST_USERS[role].email, passwords[role]);
    await api.storageState({ path: stateFile(role) });
    await api.dispose();
  }
});
