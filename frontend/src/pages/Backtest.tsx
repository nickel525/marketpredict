import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import ErrorBanner from "../components/ErrorBanner";
import MetricCard from "../components/MetricCard";
import { pct } from "../format";
import type { BacktestResponse } from "../types";

export default function BacktestPage() {
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .backtest()
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <ErrorBanner error={error} />;
  if (!data) return <div className="text-slate-400">Loading backtest…</div>;

  const { strategy, strategy_net, spy, random, config } = data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium text-white">Walk-forward backtest</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-400">
          Each week the strategy buys the model’s top {config.top_k} stocks, equal-weighted, and holds
          them for {config.hold_days} trading days. Metrics use out-of-sample predictions only.
          Transaction costs assume {config.cost_bps_per_side} bps per side on traded notional.
          Window: {config.start} to {config.end} ({config.n_weeks} weeks).
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="CAGR" value={pct(strategy.cagr)} hint="Gross" />
        <MetricCard label="Sharpe" value={fmtSharpe(strategy.sharpe)} hint="Weekly, rf = 0" />
        <MetricCard label="Max drawdown" value={pct(strategy.max_drawdown)} />
        <MetricCard label="Hit rate" value={pct(strategy.hit_rate)} hint="Weeks with positive return" />
        <MetricCard label="Weeks +5% or more" value={pct(strategy.pct_weeks_ge_5pct)} />
        <MetricCard label="Avg weekly return" value={pct(strategy.avg_weekly_return, 2)} />
      </div>

      <section className="border border-slate-800 bg-ink-900 p-4">
        <h2 className="mb-3 text-sm uppercase tracking-wide text-slate-500">Portfolio value vs S&P 500</h2>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.equity_curve}>
              <CartesianGrid stroke="#1e293b" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={28} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(value: number) => value.toFixed(2)} />
              <Tooltip
                contentStyle={{ background: "#121826", border: "1px solid #1e293b", color: "#e2e8f0" }}
                formatter={(value) => Number(value).toFixed(3)}
              />
              <Legend />
              <Line type="monotone" dataKey="strategy" name="Strategy" stroke="#34d399" dot={false} strokeWidth={1.7} />
              <Line type="monotone" dataKey="strategy_net" name="Strategy (net)" stroke="#6ee7b7" dot={false} strokeWidth={1.2} />
              <Line type="monotone" dataKey="spy" name="S&P 500" stroke="#93c5fd" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="random" name="Random 10" stroke="#94a3b8" dot={false} strokeWidth={1.2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="overflow-x-auto border border-slate-800">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-ink-900 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Series</th>
              <th className="px-4 py-3 font-medium">CAGR</th>
              <th className="px-4 py-3 font-medium">Sharpe</th>
              <th className="px-4 py-3 font-medium">Max DD</th>
              <th className="px-4 py-3 font-medium">Hit rate</th>
              <th className="px-4 py-3 font-medium">Weeks ≥ 5%</th>
            </tr>
          </thead>
          <tbody>
            <CompareRow name="Strategy (gross)" metrics={strategy} />
            <CompareRow name="Strategy (net of costs)" metrics={strategy_net} />
            <CompareRow name="S&P 500" metrics={spy} />
            <CompareRow name="Random 10" metrics={random} />
          </tbody>
        </table>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="Precision@5" value={pct(data.model.precision_at_5)} />
        <MetricCard label="Precision@10" value={pct(data.model.precision_at_10)} />
        <MetricCard label="Precision@20" value={pct(data.model.precision_at_20)} />
      </section>
    </div>
  );
}

function fmtSharpe(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : "—";
}

function CompareRow({
  name,
  metrics,
}: {
  name: string;
  metrics: BacktestResponse["strategy"];
}) {
  return (
    <tr className="border-t border-slate-800">
      <td className="px-4 py-3 text-slate-200">{name}</td>
      <td className="px-4 py-3 font-mono">{pct(metrics.cagr)}</td>
      <td className="px-4 py-3 font-mono">{fmtSharpe(metrics.sharpe)}</td>
      <td className="px-4 py-3 font-mono">{pct(metrics.max_drawdown)}</td>
      <td className="px-4 py-3 font-mono">{pct(metrics.hit_rate)}</td>
      <td className="px-4 py-3 font-mono">{pct(metrics.pct_weeks_ge_5pct)}</td>
    </tr>
  );
}
