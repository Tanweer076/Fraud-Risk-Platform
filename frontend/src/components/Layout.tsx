import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import type { Role } from "../api/client";
import { can, ROLE_LABEL, useAuth, useUser } from "../auth/context";
import { cx } from "../lib/cx";
import { type ThemePreference, useTheme } from "../lib/theme";
import { Icon, type IconName } from "./Icon";

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  show?: (role: Role) => boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: "dashboard" },
  { to: "/score", label: "Score transaction", icon: "gauge", show: can.score },
  { to: "/transactions", label: "Transactions", icon: "list" },
  { to: "/reviews", label: "Review queue", icon: "inbox" },
  { to: "/analytics", label: "Analytics", icon: "chart" },
  { to: "/models", label: "Models", icon: "model" },
  { to: "/ingestion", label: "Data ingestion", icon: "upload" },
  { to: "/admin", label: "Admin", icon: "shield", show: can.readAudit },
];

const THEME_NEXT: Record<ThemePreference, ThemePreference> = {
  system: "light",
  light: "dark",
  dark: "system",
};

const THEME_LABEL: Record<ThemePreference, string> = {
  system: "Theme: match system",
  light: "Theme: light",
  dark: "Theme: dark",
};

function ThemeButton() {
  const [theme, setTheme] = useTheme();
  return (
    <button
      type="button"
      onClick={() => setTheme(THEME_NEXT[theme])}
      className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs text-ink-2 hover:bg-subtle hover:text-ink"
      title={`${THEME_LABEL[theme]} (click to change)`}
    >
      <Icon name={theme === "dark" ? "moon" : "sun"} size={16} />
      <span>{theme === "system" ? "Auto" : theme === "dark" ? "Dark" : "Light"}</span>
      <span className="sr-only">{THEME_LABEL[theme]}, click to change</span>
    </button>
  );
}

export function Layout() {
  const user = useUser();
  const { logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const [lastPath, setLastPath] = useState(location.pathname);
  if (location.pathname !== lastPath) {
    // Close the mobile menu after navigating.
    setLastPath(location.pathname);
    setMenuOpen(false);
  }
  const items = NAV.filter((item) => !item.show || item.show(user.role));

  return (
    <div className="min-h-screen md:grid md:grid-cols-[15rem_1fr]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <aside className="border-b border-line bg-surface md:sticky md:top-0 md:flex md:h-screen md:flex-col md:border-r md:border-b-0">
        <div className="flex h-14 items-center justify-between gap-2 px-4">
          <NavLink to="/" className="flex items-center gap-2 font-semibold text-ink">
            <img src="/favicon.svg" alt="" width={22} height={22} />
            <span>Fraud Risk</span>
          </NavLink>
          <button
            type="button"
            className="rounded-md p-1.5 text-ink-2 hover:bg-subtle md:hidden"
            aria-expanded={menuOpen}
            aria-controls="main-nav"
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Icon name={menuOpen ? "close" : "menu"} />
            <span className="sr-only">Menu</span>
          </button>
        </div>
        <nav
          id="main-nav"
          aria-label="Main"
          className={cx(
            "px-2 pb-3 md:flex md:flex-1 md:flex-col md:pb-4",
            menuOpen ? "block" : "hidden md:flex",
          )}
        >
          <ul className="space-y-0.5">
            {items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cx(
                      "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm",
                      isActive
                        ? "bg-subtle font-medium text-ink"
                        : "text-ink-2 hover:bg-subtle hover:text-ink",
                    )
                  }
                >
                  <Icon name={item.icon} size={17} />
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
          <div className="mt-4 border-t border-line pt-3 md:mt-auto">
            <p className="truncate px-2.5 text-xs font-medium text-ink" title={user.email}>
              {user.full_name || user.email}
            </p>
            <p className="px-2.5 text-xs text-ink-2">{ROLE_LABEL[user.role]}</p>
            <div className="mt-2 flex items-center gap-1 px-0.5">
              <ThemeButton />
              <button
                type="button"
                onClick={logout}
                className="inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs text-ink-2 hover:bg-subtle hover:text-ink"
              >
                <Icon name="logout" size={16} />
                Sign out
              </button>
            </div>
          </div>
        </nav>
      </aside>
      <main id="main" className="min-w-0 px-4 py-6 md:px-8">
        <div className="mx-auto max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
