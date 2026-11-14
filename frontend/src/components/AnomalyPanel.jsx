import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js/dist/plotly.min.js";
import clsx from "clsx";

const Plot = createPlotlyComponent(Plotly);

// Mint theme shared by every chart, so they read as one console surface.
const BASE_LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(255,255,255,0.02)",
  font: { color: "#e2e8f0", size: 11, family: "ui-sans-serif, system-ui, sans-serif" },
  margin: { l: 52, r: 16, t: 12, b: 40 },
  showlegend: true,
  legend: { orientation: "h", y: -0.28, font: { color: "#94a3b8", size: 10 } },
  hoverlabel: {
    bgcolor: "#0a0f14",
    bordercolor: "rgba(155,247,196,0.3)",
    font: { color: "#e2e8f0" }
  }
};

const AXIS = {
  gridcolor: "rgba(255,255,255,0.08)",
  zerolinecolor: "rgba(255,255,255,0.12)",
  linecolor: "rgba(255,255,255,0.12)",
  tickfont: { color: "#94a3b8", size: 10 },
  title: { font: { color: "#94a3b8", size: 11 } }
};

const CONFIG = { displayModeBar: false, responsive: true };

function ChartCard({ title, caption, children }) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
      <div className="px-1 pb-1">
        <h3 className="text-xs font-semibold text-slate-200">{title}</h3>
        {caption && <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">{caption}</p>}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value, sub, tone }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p
        className={clsx(
          "mt-1 text-lg font-semibold",
          tone === "alert" ? "text-rose-300" : "text-slate-100"
        )}
      >
        {value}
      </p>
      {sub && <p className="text-[11px] text-slate-400">{sub}</p>}
    </div>
  );
}

/** Histogram of IsolationForest decision scores, split by flag. */
function ScoreDistributionChart({ distribution }) {
  const marked = {
    ...BASE_LAYOUT,
    barmode: "stack",
    xaxis: { ...AXIS, title: { text: "Decision score (higher = more normal)" } },
    yaxis: { ...AXIS, title: { text: "Rows" } },
    shapes: [
      {
        type: "line",
        x0: distribution.threshold,
        x1: distribution.threshold,
        y0: 0,
        y1: 1,
        yref: "paper",
        line: { color: "#f59e0b", width: 1, dash: "dot" }
      }
    ],
    annotations: [
      {
        x: distribution.threshold,
        y: 1,
        yref: "paper",
        text: `cut-off ${distribution.threshold}`,
        showarrow: false,
        font: { color: "#f59e0b", size: 10 },
        yshift: 6
      }
    ]
  };

  return (
    <ChartCard
      title="Anomaly score distribution"
      caption="Rows left of the cut-off are flagged as outliers."
    >
      <Plot
        data={[
          {
            type: "bar",
            name: "Normal",
            x: distribution.bin_centres,
            y: distribution.normal,
            marker: { color: "rgba(155,247,196,0.62)" },
            hovertemplate: "%{y} normal rows<br>score %{x}<extra></extra>"
          },
          {
            type: "bar",
            name: "Flagged",
            x: distribution.bin_centres,
            y: distribution.anomalous,
            marker: { color: "rgba(244,63,94,0.85)" },
            hovertemplate: "%{y} flagged rows<br>score %{x}<extra></extra>"
          }
        ]}
        layout={marked}
        config={CONFIG}
        style={{ width: "100%", height: 300 }}
        useResizeHandler
      />
    </ChartCard>
  );
}

/** Which features push the flagged rows away from the median. */
function ContributionChart({ contributions }) {
  const features = [...(contributions.features ?? [])].reverse();
  const layout = {
    ...BASE_LAYOUT,
    margin: { l: 12, r: 24, t: 12, b: 36 },
    showlegend: false,
    xaxis: { ...AXIS, title: { text: "Share of anomalous deviation (%)" } },
    yaxis: { ...AXIS, automargin: true, tickfont: { color: "#cbd5e1", size: 10 } }
  };

  return (
    <ChartCard
      title="Feature contributions"
      caption="Robust (MAD) deviation of flagged rows, normalised per feature."
    >
      <Plot
        data={[
          {
            type: "bar",
            orientation: "h",
            x: features.map((row) => row.contribution_percent),
            y: features.map((row) => row.feature),
            marker: {
              color: features.map((row) => row.contribution_percent),
              // Magnitude reads as one hue; rose is reserved for flagged rows.
              colorscale: [
                [0, "rgba(155,247,196,0.3)"],
                [1, "#9bf7c4"]
              ],
              showscale: false
            },
            text: features.map((row) => `${row.contribution_percent}%`),
            textposition: "outside",
            textfont: { color: "#e2e8f0", size: 10 },
            customdata: features.map((row) => [
              row.anomalous_deviation,
              row.normal_deviation
            ]),
            hovertemplate:
              "%{y}<br>%{x}% of deviation<br>flagged mean %{customdata[0]} vs normal %{customdata[1]}<extra></extra>"
          }
        ]}
        layout={layout}
        config={CONFIG}
        style={{ width: "100%", height: Math.max(220, 42 * features.length + 90) }}
        useResizeHandler
      />
    </ChartCard>
  );
}

/** The most anomalous rows, plotted by position. */
function FlaggedRowsChart({ rows }) {
  const layout = {
    ...BASE_LAYOUT,
    showlegend: false,
    xaxis: { ...AXIS, title: { text: "Row index in the uploaded CSV" } },
    yaxis: { ...AXIS, title: { text: "Decision score" } }
  };

  return (
    <ChartCard
      title="Most anomalous rows"
      caption="The lowest scores in the file — the rows most unlike the rest."
    >
      <Plot
        data={[
          {
            type: "scatter",
            mode: "markers",
            x: rows.map((row) => row.row_index),
            y: rows.map((row) => row.anomaly_score),
            marker: { color: "#f43f5e", size: 9, line: { color: "#fda4af", width: 1 } },
            hovertemplate: "row %{x}<br>score %{y}<extra></extra>"
          }
        ]}
        layout={layout}
        config={CONFIG}
        style={{ width: "100%", height: 260 }}
        useResizeHandler
      />
    </ChartCard>
  );
}

function FlaggedRowsTable({ rows, featureColumns }) {
  // Keep the table readable: every value is still available on hover in the
  // chart above, but only model features plus the score are tabulated here.
  const columns = [
    "row_index",
    ...featureColumns.filter((name) => rows.some((row) => name in row)),
    "anomaly_score"
  ];

  return (
    <section className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
      <div className="border-b border-white/10 px-4 py-3">
        <h3 className="text-xs font-semibold text-slate-200">Top flagged rows</h3>
        <p className="mt-0.5 text-[11px] text-slate-400">
          Original, unmodified values; scores are the IsolationForest decision function.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="bg-white/[0.04] text-[11px] uppercase tracking-[0.1em] text-slate-400">
              {columns.map((column) => (
                <th key={column} className="whitespace-nowrap px-3 py-2 font-medium">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr
                key={row.row_index ?? `row-${index}`}
                className="border-t border-white/10 text-slate-300 transition hover:bg-white/[0.05]"
              >
                {columns.map((column) => (
                  <td
                    key={column}
                    title={String(row[column] ?? "")}
                    className={clsx(
                      "max-w-[18rem] truncate px-3 py-2 tabular-nums",
                      column === "anomaly_score" && "text-rose-300",
                      column === "row_index" && "text-slate-400"
                    )}
                  >
                    {typeof row[column] === "number" ? row[column] : String(row[column] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/**
 * Renders the `/dataset/{id}/anomalies` payload.
 *
 * The charts are driven by the `diagnostics` block (score histogram and
 * per-feature contributions) and the `sample_outliers` rows; each chart is
 * optional so an older backend that omits diagnostics still renders the stats.
 */
export default function AnomalyPanel({ result }) {
  if (!result) return null;

  const diagnostics = result.diagnostics ?? {};
  const distribution = diagnostics.score_distribution;
  const contributions = diagnostics.feature_contributions;
  const rows = result.sample_outliers ?? [];
  const featureColumns = result.feature_columns ?? [];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Rows screened"
          value={Number(result.row_count ?? 0).toLocaleString()}
          sub={`${Number(result.scored_rows ?? 0).toLocaleString()} distinct after de-duplication`}
        />
        <Stat
          label="Outliers flagged"
          value={Number(result.anomaly_count ?? 0).toLocaleString()}
          sub={`${Number(result.anomaly_percentage ?? 0).toFixed(2)}% of the file`}
          tone="alert"
        />
        <Stat
          label="Contamination"
          value={Number(result.contamination ?? 0).toFixed(2)}
          sub="Expected outlier share used for fitting"
        />
        <Stat
          label="Model"
          value={result.method ?? "IsolationForest"}
          sub={`${featureColumns.length} numeric feature${featureColumns.length === 1 ? "" : "s"}`}
        />
      </div>

      {result.excluded_columns?.length > 0 && (
        <p className="text-[11px] leading-relaxed text-slate-400">
          <span className="font-medium text-slate-200">Excluded from the model:</span>{" "}
          {result.excluded_columns.join(", ")} — label, target and id columns would leak the answer.
        </p>
      )}

      {distribution ? (
        <ScoreDistributionChart distribution={distribution} />
      ) : (
        <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-xs text-slate-400">
          Score distribution unavailable: this response has no diagnostics block.
        </p>
      )}

      {contributions?.features?.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ContributionChart contributions={contributions} />
          <FlaggedRowsChart rows={rows} />
        </div>
      )}

      {contributions?.features?.length > 0 ? null : (
        rows.length > 0 && <FlaggedRowsChart rows={rows} />
      )}

      {rows.length > 0 ? (
        <FlaggedRowsTable rows={rows} featureColumns={featureColumns} />
      ) : (
        <p className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-xs text-slate-400">
          No flagged rows to display. Try a higher contamination value.
        </p>
      )}
    </div>
  );
}
