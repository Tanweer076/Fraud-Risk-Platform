/** A fake API for component tests: fetch is replaced by a table of routes, and every call is kept. */
import { vi } from "vitest";
import type { User } from "../api/client";

export interface Call {
  method: string;
  path: string;
  query: URLSearchParams;
  headers: Headers;
  /** Parsed JSON for JSON bodies; the raw body (FormData, URLSearchParams) otherwise. */
  body: unknown;
}

type Reply = unknown;
type Handler = Reply | ((call: Call) => Reply | Promise<Reply>);

/** A response with a status other than 200. */
export function status(code: number, body: unknown = null): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status: code,
    headers: { "Content-Type": "application/json" },
  });
}

export function page<T>(items: T[], { total = items.length, page = 1, pageSize = 50 } = {}) {
  return { items, total, page, page_size: pageSize };
}

async function toCall(input: RequestInfo | URL, init?: RequestInit): Promise<Call> {
  if (input instanceof Request) {
    const url = new URL(input.url);
    const text = input.body ? await input.clone().text() : "";
    return {
      method: input.method,
      path: url.pathname,
      query: url.searchParams,
      headers: new Headers(input.headers),
      body: text ? JSON.parse(text) : undefined,
    };
  }
  const url = new URL(String(input), window.location.origin);
  const body = init?.body;
  return {
    method: (init?.method ?? "GET").toUpperCase(),
    path: url.pathname,
    query: url.searchParams,
    headers: new Headers(init?.headers),
    body: typeof body === "string" ? JSON.parse(body) : body,
  };
}

/**
 * Routes are keyed "METHOD /path"; a value is the JSON to return, a Response, or a function of
 * the call returning either. `user` answers GET /auth/me. Unrouted calls get a 404 and are kept
 * in `unrouted`, so a test can assert none happened.
 */
export function mockApi(routes: Record<string, Handler>, { user }: { user?: User } = {}) {
  const table: Record<string, Handler> = {
    ...(user ? { "GET /api/v1/auth/me": user } : {}),
    ...routes,
  };
  const calls: Call[] = [];
  const unrouted: string[] = [];
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const call = await toCall(input, init);
    calls.push(call);
    const key = `${call.method} ${call.path}`;
    if (!(key in table)) {
      unrouted.push(key);
      return status(404, { detail: `No mock for ${key}` });
    }
    const handler = table[key];
    const reply = typeof handler === "function" ? await handler(call) : handler;
    return reply instanceof Response ? reply : status(200, reply);
  });
  return {
    calls,
    unrouted,
    fetchMock,
    /** Calls to one route, oldest first. */
    to: (method: string, path: string) =>
      calls.filter((c) => c.method === method && c.path === path),
  };
}
