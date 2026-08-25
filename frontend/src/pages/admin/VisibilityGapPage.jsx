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
          <h2 className="font-display font-semibold mb-4">Weekly trend</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate border-b border-ink-100">
                <th className="pb-2">Week</th>
                <th className="pb-2 text-right">Standard</th>
                <th className="pb-2 text-right">BDIOF</th>
                <th className="pb-2 text-right">Gap</th>
              </tr>
            </thead>
            <tbody>
              {timeseries.map((point) => (
                <tr key={point.period} className="border-b border-ink-50">
                  <td className="py-1.5 font-mono text-xs">{point.period}</td>
                  <td className="py-1.5 text-right font-mono">
                    {point.standard_shortlist_rate != null ? `${Math.round(point.standard_shortlist_rate * 100)}%` : "—"}
                  </td>
                  <td className="py-1.5 text-right font-mono">
                    {point.bdiof_shortlist_rate != null ? `${Math.round(point.bdiof_shortlist_rate * 100)}%` : "—"}
                  </td>
                  <td className="py-1.5 text-right font-mono text-beacon-600">
                    {point.visibility_gap != null ? `${Math.round(point.visibility_gap * 100)}pts` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
