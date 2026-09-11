// Temporary harness: exercises the real chart helpers (concatenated from
// VisibilityGapPage.jsx at run time) against edge-case series.

const mk = (period, s, b, ns = 5, nb = 5) => ({
  period,
  standard_shortlist_rate: s,
  bdiof_shortlist_rate: b,
  visibility_gap: s != null && b != null ? Math.round((b - s) * 1e4) / 1e4 : null,
  standard_sample_size: ns,
  bdiof_sample_size: nb,
});

const series = [
  mk("2026-W30", 0.10, 0.14),
  mk("2026-W31", 0.12, 0.21),
  mk("2026-W32", null, 0.26), // no standard-mode applications this week
  mk("2026-W33", 0.11, 0.30),
  mk("2026-W34", 0.09, null), // no bdiof-mode applications this week
  mk("2026-W35", 0.10, 0.34),
  mk("2026-W36", 0.08, 0.36),
  mk("2026-W37", 0.07, 0.39),
];

const geom = (points) => {
  const count = points.length;
  const max = yAxisMax(points);
  const x = (i) =>
    count === 1 ? CHART.padLeft + PLOT_W / 2 : CHART.padLeft + (i / (count - 1)) * PLOT_W;
  const y = (r) => CHART.padTop + (1 - r / max) * PLOT_H;
  const ticks = [];
  for (let t = 0; t <= max + 1e-9; t += TICK_STEP) ticks.push(t);
  return { count, max, x, y, ticks };
};

const g = geom(series);
console.log("yAxisMax:", g.max, "| tick labels:", g.ticks.map(asPercent).join(","));
console.log("x first/last:", g.x(0), g.x(series.length - 1), "| viewBox width:", CHART.width);
console.log("last label right edge:", g.x(series.length - 1) + 24, "(must be <=", CHART.width + ")");
console.log("y(0):", g.y(0), "= plot bottom", CHART.padTop + PLOT_H, "| y(max):", g.y(g.max), "= plot top", CHART.padTop);
console.log("standard runs:", JSON.stringify(lineRuns(series, "standard_shortlist_rate").map((r) => r.map((p) => p.index))));
console.log("bdiof runs:   ", JSON.stringify(lineRuns(series, "bdiof_shortlist_rate").map((r) => r.map((p) => p.index))));
console.log("band runs:    ", JSON.stringify(bandRuns(series).map((r) => r.map((p) => p.index))));
console.log("labels:", [...labelIndices(series.length)].sort((a, b) => a - b).map((i) => series[i].period).join(" "));

console.log("\n-- label spacing across series lengths --");
for (const n of [1, 2, 3, 7, 8, 13, 26, 52]) {
  const idx = [...labelIndices(n)].sort((a, b) => a - b);
  const gaps = idx.slice(1).map((v, i) => v - idx[i]);
  console.log(
    `n=${String(n).padStart(2)} -> [${idx.join(",")}] min gap ${gaps.length ? Math.min(...gaps) : "-"}`,
    `| first&last labelled: ${idx[0] === 0 && idx[idx.length - 1] === n - 1}`,
  );
}

console.log("\n-- single bucket --");
const one = [mk("2026-W37", 0.2, 0.35)];
const g1 = geom(one);
console.log(
  "centred x:", g1.x(0), "(plot centre", CHART.padLeft + PLOT_W / 2, ")",
  "| drawable lines:", lineRuns(one, "standard_shortlist_rate").filter((r) => r.length > 1).length,
  "| band runs:", bandRuns(one).length,
);

console.log("\n-- modes never co-occur, so no gap is defined --");
const disjoint = [mk("2026-W30", 0.1, null), mk("2026-W31", null, 0.3)];
console.log("band runs:", bandRuns(disjoint).length);
console.log("aria summary:", chartSummary(disjoint));

console.log("\n-- a real 0% rate must plot, not be treated as missing --");
const zero = [mk("2026-W30", 0, 0.1), mk("2026-W31", 0, 0.2)];
console.log(
  "standard values kept:", JSON.stringify(lineRuns(zero, "standard_shortlist_rate").map((r) => r.map((p) => p.value))),
  "| band runs:", bandRuns(zero).length,
);

console.log("\n-- negative gap (anonymised screening doing worse) --");
console.log(pointSummary(mk("2026-W30", 0.3, 0.2)));
console.log("yAxisMax at 78%:", geom([mk("a", 0.78, 0.4)]).max, "| at 100%:", geom([mk("a", 1, 1)]).max);
console.log("\naria summary (main series):", chartSummary(series));
