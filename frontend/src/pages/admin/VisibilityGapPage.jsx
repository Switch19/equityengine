import { useState, useEffect, useCallback } from "react";
import { adminApi } from "../../api/admin";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";

export default function VisibilityGapPage() {
  const [gap, setGap] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const [gapRes, tsRes] = await Promise.all([
        adminApi.getVisibilityGap(),
        adminApi.getVisibilityGapTimeseries("week"),
      ]);
      setGap(gapRes.data);
      setTimeseries(tsRes.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <LoadingSkeleton lines={5} />
      </div>
    );
  }

  const modes = gap ? Object.entries(gap.rates_by_mode) : [];
  const maxRate = Math.max(0.01, ...modes.map(([, d]) => d.shortlist_rate || 0));

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Visibility Gap</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        Shortlist rate comparison across screening modes.
      </p>

      <div className="card p-6">
        <div className="text-center mb-6">
          <p className="text-sm text-slate">Visibility Gap (BDIOF − Standard)</p>
          <p className="score-figure text-4xl text-beacon-600 mt-1">
            {gap.visibility_gap != null ? `${Math.round(gap.visibility_gap * 100)} pts` : "—"}
          </p>
          {gap.visibility_gap_percent_improvement != null && (
            <p className="text-sm text-verified mt-1">
              +{gap.visibility_gap_percent_improvement}% relative improvement
            </p>
          )}
        </div>

        <div className="space-y-4">
          {modes.map(([mode, data]) => (
            <div key={mode}>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium capitalize">{mode}</span>
                <span className="font-mono">
                  {data.shortlist_rate != null ? `${Math.round(data.shortlist_rate * 100)}%` : "no data"}
                  <span className="text-slate ml-1">(n={data.total_applications})</span>
                </span>
              </div>
              <div className="h-3 bg-ink-50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-ink-400"
                  style={{ width: `${((data.shortlist_rate || 0) / maxRate) * 100}%` }}
                />
              </div>
              {data.small_sample && (
                <p className="text-xs text-gap mt-1">Small sample — treat as preliminary.</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {gap.warnings?.length > 0 && (
        <div className="mt-4 text-sm bg-gap-50 text-gap rounded p-4 space-y-1">
          {gap.warnings.map((w, i) => <p key={i}>{w}</p>)}
        </div>
      )}

      <p className="text-xs text-slate mt-4 leading-relaxed">{gap.methodology_note}</p>

      {timeseries.length > 0 && (
        <div className="card p-6 mt-6">
          <h2 className="font-display font-semibold mb-1">Weekly trend</h2>
          <p className="text-xs text-slate mb-4">
            Shortlist rate per screening mode, by week of application. The shaded band is the
            Visibility Gap — where it widens, anonymised screening is selecting candidates that
            standard screening passed over.
          </p>
          <TrendChart points={timeseries} />
          <TrendTable points={timeseries} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------
// Weekly trend chart
// ---------------------------------------------------------------------

// padRight leaves room for the final period label, which is centred on
// the last data point and would otherwise overflow the viewBox.
const CHART = { width: 720, height: 250, padLeft: 44, padRight: 30, padTop: 14, padBottom: 38 };
const PLOT_W = CHART.width - CHART.padLeft - CHART.padRight;
const PLOT_H = CHART.height - CHART.padTop - CHART.padBottom;
const TICK_STEP = 0.25;

// Tailwind tokens aren't reachable from SVG presentation attributes, so
// the palette is mirrored here from tailwind.config.js.
const COLOR = {
  grid: "#E1E2EF",
  axis: "#5C5F8C",
  label: "#6B6F8A",
  standard: "#5C5F8C",
  bdiof: "#C79300",
  band: "#FEF9E7",
};

const asPercent = (rate) => Math.round((rate ?? 0) * 100);

/**
 * Y-axis maximum, rounded up to the next quarter above the largest
 * plotted rate. A fixed 0-100% axis would squash typical shortlist
 * rates (often 10-35%) into the bottom sliver of the plot, while
 * quarter steps keep every gridline label a whole percentage.
 */
function yAxisMax(points) {
  const rates = points
    .flatMap((p) => [p.standard_shortlist_rate, p.bdiof_shortlist_rate])
    .filter((r) => r != null);
  const dataMax = rates.length ? Math.max(...rates) : 0;
  return Math.min(1, Math.max(TICK_STEP, Math.ceil(dataMax / TICK_STEP) * TICK_STEP));
}

/**
 * Splits a series into runs of consecutive periods that actually have a
 * rate. A mode with no applications in a week returns null, which must
 * break the line rather than plot as 0% — drawing through it would
 * invent a decline to zero that the data does not claim.
 */
function lineRuns(points, key) {
  const runs = [];
  let current = [];
  points.forEach((point, index) => {
    if (point[key] == null) {
      if (current.length) runs.push(current);
      current = [];
    } else {
      current.push({ index, value: point[key] });
    }
  });
  if (current.length) runs.push(current);
  return runs;
}

/** Runs where BOTH modes have a rate, so the gap between them is defined. */
function bandRuns(points) {
  const runs = [];
  let current = [];
  points.forEach((point, index) => {
    const { standard_shortlist_rate: standard, bdiof_shortlist_rate: bdiof } = point;
    if (standard != null && bdiof != null) {
      current.push({ index, standard, bdiof });
    } else {
      if (current.length > 1) runs.push(current);
      current = [];
    }
  });
  if (current.length > 1) runs.push(current);
  return runs;
}

/**
 * First and last period always get an x-axis label, with roughly six
 * across the plot. When honouring the last one would crowd its
 * neighbour, the neighbour is dropped instead of overlapping it.
 */
function labelIndices(count) {
  const every = Math.max(1, Math.ceil(count / 6));
  const indices = new Set();
  for (let i = 0; i < count; i += every) indices.add(i);
  if (count > 1 && !indices.has(count - 1)) {
    const last = Math.max(...indices);
    if (count - 1 - last < every) indices.delete(last);
    indices.add(count - 1);
  }
  return indices;
}

function pointSummary(point) {
  const rate = (value) => (value != null ? `${asPercent(value)}%` : "no data");
  const gap = point.visibility_gap != null ? `${asPercent(point.visibility_gap)}pts` : "n/a";
  return (
    `${point.period} — Standard ${rate(point.standard_shortlist_rate)} ` +
    `(n=${point.standard_sample_size}), BDIOF ${rate(point.bdiof_shortlist_rate)} ` +
    `(n=${point.bdiof_sample_size}), gap ${gap}`
  );
}

function chartSummary(points) {
  const withGap = points.filter((p) => p.visibility_gap != null);
  if (withGap.length === 0) {
    return "Weekly shortlist rate trend. No week yet has applications under both screening modes, so no gap can be plotted.";
  }
  const first = withGap[0];
  const last = withGap[withGap.length - 1];
  return (
    `Weekly shortlist rate trend across ${points.length} periods. ` +
    `Visibility Gap moves from ${asPercent(first.visibility_gap)} points in ${first.period} ` +
    `to ${asPercent(last.visibility_gap)} points in ${last.period}.`
  );
}

function TrendChart({ points }) {
  const count = points.length;
  const max = yAxisMax(points);

  const ticks = [];
  for (let tick = 0; tick <= max + 1e-9; tick += TICK_STEP) ticks.push(tick);

  // A single bucket has no span to interpolate across, so it is centred
  // and rendered as points only — there is no line to draw through one
  // observation, and stretching one across the plot would imply a trend.
  const x = (index) =>
    count === 1 ? CHART.padLeft + PLOT_W / 2 : CHART.padLeft + (index / (count - 1)) * PLOT_W;
  const y = (rate) => CHART.padTop + (1 - rate / max) * PLOT_H;

  const columnHalf = Math.max(6, (count === 1 ? PLOT_W : PLOT_W / (count - 1)) / 2);
  const labelled = labelIndices(count);
  const path = (coords) => `M ${coords.join(" L ")} Z`;

  return (
    <>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${CHART.width} ${CHART.height}`}
          className="w-full h-auto min-w-[420px]"
          role="img"
          aria-label={chartSummary(points)}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={CHART.padLeft}
                x2={CHART.width - CHART.padRight}
                y1={y(tick)}
                y2={y(tick)}
                stroke={tick === 0 ? COLOR.axis : COLOR.grid}
                strokeWidth="1"
              />
              <text
                x={CHART.padLeft - 8}
                y={y(tick) + 3.5}
                textAnchor="end"
                fontSize="10"
                fontFamily="IBM Plex Mono, monospace"
                fill={COLOR.label}
              >
                {asPercent(tick)}%
              </text>
            </g>
          ))}

          {bandRuns(points).map((run) => (
            <path
              key={`band-${run[0].index}`}
              d={path([
                ...run.map((p) => `${x(p.index)},${y(p.bdiof)}`),
                ...[...run].reverse().map((p) => `${x(p.index)},${y(p.standard)}`),
              ])}
              fill={COLOR.band}
            />
          ))}

          {lineRuns(points, "standard_shortlist_rate").map(
            (run) =>
              run.length > 1 && (
                <polyline
                  key={`standard-${run[0].index}`}
                  points={run.map((p) => `${x(p.index)},${y(p.value)}`).join(" ")}
                  fill="none"
                  stroke={COLOR.standard}
                  strokeWidth="2"
                  strokeDasharray="5 4"
                  strokeLinecap="round"
                />
              ),
          )}

          {lineRuns(points, "bdiof_shortlist_rate").map(
            (run) =>
              run.length > 1 && (
                <polyline
                  key={`bdiof-${run[0].index}`}
                  points={run.map((p) => `${x(p.index)},${y(p.value)}`).join(" ")}
                  fill="none"
                  stroke={COLOR.bdiof}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              ),
          )}

          {points.map((point, index) => {
            // Hover column, clamped to the plot area so the end columns
            // don't sit invisibly on top of the y-axis labels.
            const left = Math.max(CHART.padLeft, x(index) - columnHalf);
            const right = Math.min(CHART.width - CHART.padRight, x(index) + columnHalf);
            return (
              <g key={point.period}>
                <title>{pointSummary(point)}</title>
                <rect
                  x={left}
                  y={CHART.padTop}
                  width={right - left}
                  height={PLOT_H}
                  fill="transparent"
                />
                {point.standard_shortlist_rate != null && (
                  <circle
                    cx={x(index)}
                    cy={y(point.standard_shortlist_rate)}
                    r="3"
                    fill="#FFFFFF"
                    stroke={COLOR.standard}
                    strokeWidth="2"
                  />
                )}
                {point.bdiof_shortlist_rate != null && (
                  <circle
                    cx={x(index)}
                    cy={y(point.bdiof_shortlist_rate)}
                    r="3.5"
                    fill={COLOR.bdiof}
                  />
                )}
              </g>
            );
          })}

          {points.map(
            (point, index) =>
              labelled.has(index) && (
                <text
                  key={`label-${point.period}`}
                  x={x(index)}
                  y={CHART.height - CHART.padBottom + 18}
                  textAnchor="middle"
                  fontSize="10"
                  fontFamily="IBM Plex Mono, monospace"
                  fill={COLOR.label}
                >
                  {point.period}
                </text>
              ),
          )}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mt-2 text-xs text-slate">
        <span className="inline-flex items-center gap-2">
          <span className="inline-block w-5 border-t-2 border-dashed border-ink-400" />
          Standard
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="inline-block w-5 h-0.5 bg-beacon-600" />
          BDIOF (anonymised)
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="inline-block w-4 h-3 bg-beacon-50 border border-ink-100 rounded-sm" />
          Visibility Gap
        </span>
      </div>
    </>
  );
}

/**
 * The exact figures, kept behind a disclosure. The chart is what the
 * room looks at; an audit tool still has to be able to show the numbers
 * it drew, and a line chart is not readable by a screen reader.
 */
function TrendTable({ points }) {
  return (
    <details className="mt-4">
      <summary className="text-xs text-slate cursor-pointer hover:text-ink">
        Show underlying figures
      </summary>
      <table className="w-full text-sm mt-3">
        <thead>
          <tr className="text-left text-xs text-slate border-b border-ink-100">
            <th className="pb-2">Week</th>
            <th className="pb-2 text-right">Standard</th>
            <th className="pb-2 text-right">BDIOF</th>
            <th className="pb-2 text-right">Gap</th>
            <th className="pb-2 text-right">n</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.period} className="border-b border-ink-50">
              <td className="py-1.5 font-mono text-xs">{point.period}</td>
              <td className="py-1.5 text-right font-mono">
                {point.standard_shortlist_rate != null ? `${asPercent(point.standard_shortlist_rate)}%` : "—"}
              </td>
              <td className="py-1.5 text-right font-mono">
                {point.bdiof_shortlist_rate != null ? `${asPercent(point.bdiof_shortlist_rate)}%` : "—"}
              </td>
              <td className="py-1.5 text-right font-mono text-beacon-600">
                {point.visibility_gap != null ? `${asPercent(point.visibility_gap)}pts` : "—"}
              </td>
              <td className="py-1.5 text-right font-mono text-xs text-slate">
                {point.standard_sample_size}/{point.bdiof_sample_size}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
