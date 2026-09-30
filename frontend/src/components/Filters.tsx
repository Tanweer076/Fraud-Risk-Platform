/** Filter controls for a filter row: they read from and write to the URL through their owner. */
import { type ReactNode, useState } from "react";
import { cx } from "../lib/cx";
import { Input, Select } from "./ui";

/** A text filter that applies on Enter or when the field loses focus, not on every keystroke. */
export function TextFilter({
  label,
  value,
  onApply,
  placeholder,
  className,
}: {
  label: string;
  value: string | undefined;
  onApply: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  const [draft, setDraft] = useState(value ?? "");
  const [synced, setSynced] = useState(value);
  if (value !== synced) {
    // The URL changed (cleared, or back button): show its value.
    setSynced(value);
    setDraft(value ?? "");
  }
  const apply = () => {
    if (draft.trim() !== (value ?? "")) onApply(draft.trim());
  };
  return (
    <label className={cx("block", className)}>
      <span className="mb-1 block text-xs font-medium text-ink-2">{label}</span>
      <Input
        value={draft}
        placeholder={placeholder}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={apply}
        onKeyDown={(event) => {
          if (event.key === "Enter") apply();
        }}
      />
    </label>
  );
}

export function SelectFilter({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-2">{label}</span>
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </Select>
    </label>
  );
}
