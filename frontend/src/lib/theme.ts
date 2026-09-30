import { useCallback, useEffect, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";

const KEY = "theme";

function readPreference(): ThemePreference {
  try {
    const saved = localStorage.getItem(KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

function systemIsDark(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

function apply(preference: ThemePreference) {
  const dark = preference === "dark" || (preference === "system" && systemIsDark());
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

/** The viewer's colour theme; "system" follows the OS setting, including later changes. */
export function useTheme(): [ThemePreference, (preference: ThemePreference) => void] {
  const [preference, setPreference] = useState<ThemePreference>(readPreference);

  useEffect(() => {
    apply(preference);
    if (preference !== "system" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => apply("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [preference]);

  const update = useCallback((next: ThemePreference) => {
    try {
      if (next === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch {
      // Applies for this page view only.
    }
    setPreference(next);
  }, []);

  return [preference, update];
}
