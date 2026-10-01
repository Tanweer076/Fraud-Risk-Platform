import { type ReactNode, useState } from "react";
import { cx, table as t } from "../../lib/cx";
import { Icon } from "../Icon";

export interface TableColumn {
  key: string;
  label: string;
  numeric?: boolean;
}

export interface ChartTable {
  columns: TableColumn[];
  rows: Record<string, ReactNode>[];
}

/**
 * A chart with its title and a table view of the same numbers (for screen readers, exact values
 * and colour-blind readers). While new data loads, the previous chart stays up, dimmed.
 */
export function ChartCard({
  title,
  subtitle,
  table,
  children,
  refreshing = false,
  actions,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  table: ChartTable;
  children: ReactNode;
  refreshing?: boolean;
  actions?: ReactNode;
  className?: string;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure
      className={cx("flex min-w-0 flex-col rounded-lg border border-line bg-surface", className)}
    >
      <figcaption className="flex flex-wrap items-start justify-between gap-2 px-4 pt-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-ink-2">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          <button
            type="button"
            onClick={() => setShowTable((shown) => !shown)}
            className="inline-flex h-7 items-center gap-1 rounded-md border border-line px-2 text-xs text-ink-2 hover:bg-subtle hover:text-ink"
          >
            <Icon name="table" size={14} />
            {showTable ? "Show chart" : "Show table"}
          </button>
        </div>
      </figcaption>
      <div
        className={cx(
          "min-w-0 flex-1 px-4 pt-2 pb-4 transition-opacity",
          refreshing && "opacity-60",
        )}
      >
        {showTable ? <DataTable table={table} /> : children}
      </div>
    </figure>
  );
}

export function DataTable({ table }: { table: ChartTable }) {
  return (
    <div className={cx(t.wrap, "max-h-80 overflow-y-auto")}>
      <table className={t.table}>
        <thead className="sticky top-0 bg-surface">
          <tr>
            {table.columns.map((column) => (
              <th key={column.key} scope="col" className={cx(t.th, column.numeric && t.num)}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, index) => (
            <tr key={index}>
              {table.columns.map((column) => (
                <td key={column.key} className={cx(t.td, "py-1.5", column.numeric && t.num)}>
                  {row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
