/** Join class names, skipping falsy ones. */
export function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

/** Table styling shared by every list. */
export const table = {
  // relative: screen-reader-only text inside must not stretch the page past the scroller.
  wrap: "relative overflow-x-auto",
  table: "w-full border-collapse text-left text-sm",
  th: "border-b border-line px-3 py-2 text-xs font-medium whitespace-nowrap text-ink-2",
  td: "border-b border-line px-3 py-2 align-top",
  num: "text-right",
  row: "hover:bg-subtle",
};
