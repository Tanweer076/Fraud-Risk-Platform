import { BAND_COLOR, BAND_LABEL, BAND_MIN, BANDS, bandFor } from "../lib/bands";
import { cx } from "../lib/cx";
import { BandIcon } from "./BandBadge";

/**
 * The 0-100 risk score as a meter: the fill carries the band's status colour, the track shows
 * where each band starts, and the band is named in text beside the number.
 */
export function RiskGauge({ score }: { score: number }) {
  const band = bandFor(score);
  return (
    <div>
      <div className="flex items-end gap-3">
        <span className="text-5xl leading-none font-semibold text-ink">{score}</span>
        <span className="mb-1 inline-flex items-center gap-1.5 text-sm font-medium text-ink">
          <BandIcon band={band} size={16} />
          {BAND_LABEL[band]} risk
        </span>
      </div>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score}
        aria-valuetext={`${score} out of 100, ${BAND_LABEL[band]} risk`}
        className="relative mt-4 h-2.5 rounded-full bg-subtle"
      >
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${Math.max(2, score)}%`, background: BAND_COLOR[band] }}
        />
        {BANDS.slice(1).map((b) => (
          <span
            key={b}
            className="absolute -top-1 h-4.5 w-0.5 bg-surface"
            style={{ left: `calc(${BAND_MIN[b]}% - 1px)` }}
            aria-hidden="true"
          />
        ))}
      </div>
      {/* Where each band starts, centred under its tick. */}
      <div className="relative mt-1 h-4 text-[11px] text-ink-3" aria-hidden="true">
        {BANDS.map((b) => (
          <span
            key={b}
            className={cx("absolute", BAND_MIN[b] > 0 && "-translate-x-1/2")}
            style={{ left: `${BAND_MIN[b]}%` }}
          >
            {BAND_MIN[b]}
          </span>
        ))}
      </div>
    </div>
  );
}
