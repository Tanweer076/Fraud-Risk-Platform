"""Render the EDA results as one self-contained HTML file (charts embedded as PNG)."""

import base64
import html
import io
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from fraudml.eda import analysis as A  # noqa: E402

INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]

SEGMENT_TITLES = {
    "currency": "Currency",
    "country": "Country",
    "description": "Description",
    "weekday": "Weekday",
    "amount_band": "Amount band",
    "month_part": "Part of month",
}


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=144, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _img(b64: str, alt: str) -> str:
    return f'<img alt="{html.escape(alt)}" src="data:image/png;base64,{b64}">'


def chart_break_types(counts: pd.DataFrame) -> str:
    counts = counts.loc[:, counts.sum() > 0]
    counts = counts[counts.sum(axis=1) > 0].sort_values(counts.columns[-1])
    fig, ax = plt.subplots(figsize=(7.5, 0.45 * len(counts) + 1))
    height = 0.8 / len(counts.columns)
    for i, period in enumerate(counts.columns):
        # First period sits on top within each group, matching the legend order.
        y = [j + ((len(counts.columns) - 1) / 2 - i) * height for j in range(len(counts))]
        bars = ax.barh(y, counts[period], height=height * 0.9, color=SERIES[i], label=period)
        ax.bar_label(bars, padding=3, fontsize=8, color=INK_2)
    ax.set_yticks(range(len(counts)), [t.replace("_", " ") for t in counts.index])
    ax.legend(frameon=False, fontsize=9, loc="lower right", labelcolor=INK)
    ax.set_xlabel("Transactions", color=INK_2, fontsize=9)
    _style(ax)
    return _img(_png(fig), "Break type counts per month")


def chart_segments(df: pd.DataFrame) -> str:
    overall = df["is_suspicious"].mean()
    fig, axes = plt.subplots(2, 3, figsize=(11, 8.5))
    for ax, seg in zip(axes.flat, A.SEGMENTS, strict=True):
        r = A.segment_rates(df, seg)
        r = r[r["transactions"] >= 30].sort_values("rate")
        y = range(len(r))
        ax.hlines(y, r["ci_low"] * 100, r["ci_high"] * 100, color=SERIES[0], alpha=0.35, lw=3)
        ax.plot(r["rate"] * 100, y, "o", color=SERIES[0], ms=5)
        ax.axvline(overall * 100, color=INK_2, lw=1, ls="--")
        ax.set_yticks(list(y), [str(v) for v in r.index], fontsize=8)
        ax.set_title(SEGMENT_TITLES[seg], loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Suspicious rate, % (95% interval)", color=INK_2, fontsize=8)
        _style(ax)
    fig.text(0.01, 0.005, f"Dashed line: overall rate {overall:.1%}", color=INK_2, fontsize=8)
    fig.tight_layout()
    return _img(_png(fig), "Suspicious rate by segment with 95% intervals")


def chart_histogram(values: pd.Series, xlabel: str, bins: int, alt: str) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 3))
    ax.hist(values, bins=bins, color=SERIES[0], edgecolor=SURFACE, linewidth=1)
    ax.set_xlabel(xlabel, color=INK_2, fontsize=9)
    ax.set_ylabel("Transactions", color=INK_2, fontsize=9)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    return _img(_png(fig), alt)


def _table(df: pd.DataFrame, pct: tuple[str, ...] = (), dec: tuple[str, ...] = ()) -> str:
    fmt = {"count": "{:,.0f}".format} | {c: "{:.1%}".format for c in pct}
    fmt |= {c: "{:.3f}".format for c in dec}
    return df.to_html(formatters=fmt, border=0, classes="t", na_rep="–")


def _spread(values: pd.Series) -> pd.Series:
    return pd.Series(
        {
            "count": len(values),
            "median": values.median(),
            "p90": values.quantile(0.9),
            "max": values.max(),
        }
    )


def findings(df: pd.DataFrame, labelled: pd.DataFrame) -> list[str]:
    ov = A.overview(df)
    types = A.break_type_counts(labelled)
    co = A.co_occurrence(labelled)
    spread = A.segment_spread(labelled)
    hist = A.account_history_effect(df).dropna()
    drift = A.drift(df)
    patterns = A.presence_patterns(df)
    single = patterns.loc[[i for i in patterns.index if "+" not in i]].to_numpy().sum()

    rates = ", ".join(f"{p}: {r:.1%}" for p, r in ov["suspicious_rate"].items())
    top = types.sum(axis=1).sort_values(ascending=False)
    rv = co.loc["rule_violation", "rule_violation"]
    rv_amt = co.loc["rule_violation", "amount_mismatch"]
    out = [
        f"{int(ov['transactions'].sum()):,} transactions over {len(ov)} months. "
        f"Suspicious rate by month: {rates}. The rate is rising, so validation must be "
        "time-based and metrics must suit heavy imbalance (PR-AUC).",
        f"Most common break types: {top.index[0].replace('_', ' ')} ({int(top.iloc[0]):,}), "
        f"{top.index[1].replace('_', ' ')} ({int(top.iloc[1]):,}), "
        f"{top.index[2].replace('_', ' ')} ({int(top.iloc[2]):,}).",
        f"{int(rv_amt):,} of {int(rv):,} rule violations are also amount mismatches: one "
        "system records a negative or over-limit amount while the others do not.",
        f"{int(single):,} transactions exist in only one system.",
        "Single-system attributes barely move the rate: across currency, country, "
        "description, weekday, amount band and part of month, rates stay between "
        f"{spread['min_rate'].min():.1%} and {spread['max_rate'].max():.1%}.",
    ]
    if not hist.empty:
        last = hist[hist["period"] == hist["period"].max()].set_index("account_group")["rate"]
        out.append(
            f"Account history does not predict breaks: in {hist['period'].max()}, accounts that "
            f"broke the month before had a {last.get('broke last month', float('nan')):.1%} "
            f"rate versus {last.get('did not', float('nan')):.1%} for the rest."
        )
    if not drift.empty:
        out.append(
            f"Amount distributions are stable month to month (largest PSI "
            f"{drift.to_numpy().max():.3f}; below 0.1 means no meaningful drift)."
        )
    out.append(
        "Modelling implication: the signal is in cross-system deviations (missing "
        "counterparts, amount/date/currency deltas, key-map gaps) and rule checks, not in "
        "the transaction's own attributes or account history."
    )
    return out


CSS = """
:root { color-scheme: light; }
body { margin: 0; background: #fcfcfb; color: #0b0b0b;
       font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 19px; margin: 40px 0 8px; border-top: 1px solid #e4e3df; padding-top: 24px; }
p.meta, p.note { color: #52514e; font-size: 13px; }
img { max-width: 100%; height: auto; display: block; margin: 12px 0; }
table.t { border-collapse: collapse; font-size: 13px; margin: 8px 0;
          font-variant-numeric: tabular-nums; }
table.t th, table.t td { padding: 4px 10px; border-bottom: 1px solid #e4e3df; text-align: right; }
table.t th:first-child, table.t tbody th { text-align: left; }
.scroll { overflow-x: auto; }
ul.findings li { margin-bottom: 6px; }
"""


def render(df: pd.DataFrame) -> str:
    labelled = df[df.groupby("period")["is_suspicious"].transform("any")]
    ov = A.overview(df)
    types = A.break_type_counts(df)
    deltas = A.amount_deltas(labelled)
    gaps = A.date_deltas(labelled)
    periods = ", ".join(sorted(df["period"].unique()))
    labelled_periods = ", ".join(sorted(labelled["period"].unique()))

    sections = [
        f"<h1>EDA report</h1><p class='meta'>Periods {periods} · generated "
        f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC</p>",
        "<h2>Key findings</h2><ul class='findings'>"
        + "".join(f"<li>{html.escape(f)}</li>" for f in findings(df, labelled))
        + "</ul>",
        "<h2>Volumes and suspicious rate</h2><div class='scroll'>"
        + _table(ov, pct=("suspicious_rate",))
        + "</div><p class='note'>in_gl / in_ma / in_fa: transactions present in each system.</p>",
        "<h2>Which systems hold each transaction</h2><div class='scroll'>"
        + _table(A.presence_patterns(df))
        + "</div>",
        "<h2>Break types</h2>"
        + chart_break_types(types)
        + "<div class='scroll'>"
        + _table(types)
        + "</div>",
        "<h3>Break types per suspicious transaction</h3><div class='scroll'>"
        + _table(A.break_multiplicity(df))
        + "</div>",
        "<h3>Break types that occur together</h3><p class='note'>Suspicious transactions "
        "carrying both types; the diagonal is each type's total.</p><div class='scroll'>"
        + _table(A.co_occurrence(labelled))
        + "</div>",
        f"<h2>Does the rate vary by segment?</h2><p class='note'>Months with breaks only "
        f"({labelled_periods}); segment values with at least 30 transactions.</p>"
        + chart_segments(labelled)
        + "<div class='scroll'>"
        + _table(A.segment_spread(labelled), pct=("min_rate", "max_rate"))
        + "</div>"
        + "<p class='note'>values_outside_ci: values whose 95% interval excludes the overall "
        "rate. With many values a few can land outside by chance.</p>",
        "<h2>Size of amount mismatches</h2><p class='note'>Largest pairwise difference "
        "divided by the larger amount. Near 1.0 means one amount is many times the other; "
        "above 1.0 means the amounts have opposite signs.</p>"
        + chart_histogram(
            deltas["max_rel_delta"],
            "Relative difference",
            40,
            "Distribution of relative amount differences",
        )
        + "<div class='scroll'>"
        + _table(
            deltas.groupby("period")["max_rel_delta"].apply(_spread).unstack(),
            dec=("median", "p90", "max"),
        )
        + "</div>",
        "<h2>Size of date mismatches</h2>"
        + chart_histogram(
            gaps, "Largest gap between systems (days)", 30, "Distribution of date gaps"
        )
        + "<div class='scroll'>"
        + _table(_spread(gaps).to_frame("days").T)
        + "</div>",
        "<h2>Account history</h2><p class='note'>Suspicious rate this month for accounts "
        "that did or did not have a suspicious transaction the month before.</p>"
        "<div class='scroll'>"
        + _table(A.account_history_effect(df).set_index(["period", "account_group"]), pct=("rate",))
        + "</div>",
        "<h2>Drift against the first month</h2><p class='note'>Population stability index "
        "of amounts; under 0.1 is stable, over 0.25 is a large shift.</p><div class='scroll'>"
        + _table(A.drift(df), dec=tuple(f"amount_{s}_psi" for s in ("gl", "ma", "fa")))
        + "</div>",
    ]
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>EDA Report</title><style>{CSS}</style></head><body><main>"
        + "".join(sections)
        + "</main></body></html>"
    )


def write_report(processed_dir: str | Path, out: str | Path) -> Path:
    df = A.load_labelled(processed_dir)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(df), encoding="utf-8")
    return out
