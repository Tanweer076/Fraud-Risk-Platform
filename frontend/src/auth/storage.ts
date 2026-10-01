import type { Session } from "./context";

const KEY = "fraud-risk-session";

/**
 * The session lives in sessionStorage: it survives a reload but not closing the tab, and it is
 * never shared across tabs. Storage can be unavailable (private mode), so every access is guarded.
 */
export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    if (!session.token || !session.user || session.expiresAt <= Date.now()) return null;
    return session;
  } catch {
    return null;
  }
}

export function saveSession(session: Session) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    // Still signed in for this page view.
  }
}

export function clearSession() {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Nothing stored.
  }
}
