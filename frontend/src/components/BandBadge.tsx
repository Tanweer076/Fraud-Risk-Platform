import type { Band } from "../api/client";
import { BAND_COLOR, BAND_LABEL, isBand } from "../lib/bands";
import { cx } from "../lib/cx";
import { DASH } from "../lib/format";

/**
 * Each band has its own shape as well as its status colour, so the band never depends on colour
 * alone: circle-check (low), triangle (medium), diamond (high), octagon (critical).
 */
export function BandIcon({ band, size = 14 }: { band: Band; size?: number }) {
  const fill = BAND_COLOR[band];
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" className="shrink-0">
      {band === "low" && (
        <>
          <circle cx="8" cy="8" r="7" fill={fill} />
          <path
            d="M4.8 8.2 7 10.3l4.2-4.4"
            fill="none"
            stroke="#fff"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
      {band === "medium" && (
        <>
          <path d="M8 1.2 15.2 14H.8Z" fill={fill} strokeLinejoin="round" />
          <path d="M8 5.8v3.8M8 11.6v.1" stroke="#0b0b0b" strokeWidth="1.7" strokeLinecap="round" />
        </>
      )}
      {band === "high" && (
        <>
          <path d="M8 .8 15.2 8 8 15.2.8 8Z" fill={fill} />
          <path d="M8 4.6v4.2M8 11v.1" stroke="#0b0b0b" strokeWidth="1.7" strokeLinecap="round" />
        </>
      )}
      {band === "critical" && (
        <>
          <path d="M5.1 1h5.8L15 5.1v5.8L10.9 15H5.1L1 10.9V5.1Z" fill={fill} />
          <path
            d="m5.6 5.6 4.8 4.8m0-4.8-4.8 4.8"
            stroke="#fff"
            strokeWidth="1.7"
            strokeLinecap="round"
          />
        </>
      )}
    </svg>
  );
}

/** Band with its label, and the score when given: "92 Critical". */
export function BandBadge({
  band,
  score,
  className,
}: {
  band: string | null | undefined;
  score?: number | null;
  className?: string;
}) {
  if (!isBand(band)) return <span className="text-ink-3">{score ?? DASH}</span>;
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border border-line bg-surface py-0.5 pr-2 pl-1.5 text-xs whitespace-nowrap text-ink",
        className,
      )}
    >
      <BandIcon band={band} />
      {score != null && <span className="font-semibold tabular-nums">{score}</span>}
      <span className={score != null ? "text-ink-2" : undefined}>{BAND_LABEL[band]}</span>
    </span>
  );
}
