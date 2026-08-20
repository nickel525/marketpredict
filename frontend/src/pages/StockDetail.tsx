import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CartesianGrid,
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
import { compact, num, pct, signedClass } from "../format";
import type { StockDetail } from "../types";

export default function StockDetailPage() {
  const { ticker } = useParams();
  const [data, setData] = useState<StockDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;
    setData(null);
    api
      .stock(ticker)
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, [ticker]);

  if (error) return <ErrorBanner error={error} />;
  if (!data) return <div className="text-slate-400">Loading {ticker}…</div>;

  const important = data.features.slice(0, 8);

  return (
    <div className="space-y-6">
      <div>
        <Link to="/" className="text-sm text-slate-500 hover:text-slate-300">
          ← Rankings
        </Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-medium text-white">
              {data.ticker} <span className="text-slate-400">{data.name}</span>
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {data.sector} · as of {data.as_of}
            </p>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase tracking-wide text-slate-500">Model probability</div>
            <div className="font-mono text-3xl text-emerald-400">{pct(data.probability)}</div>
          </div>
        </div>
      </div>

      <p className="max-w-3xl text-sm leading-6 text-slate-300">{data.explanation}</p>

      <div className="grid gap-3 sm:grid-cols-4">
        <MetricCard label="Price" value={num(data.price)} />
        <MetricCard label="1-day" value={pct(data.returns["1d"])} />
        <MetricCard label="5-day" value={pct(data.returns["5d"])} />
        <MetricCard label="20-day" value={pct(data.returns["20d"])} />
      </div>

      <section className="border border-slate-800 bg-ink-900 p-4">
        <h2 className="mb-3 text-sm uppercase tracking-wide text-slate-500">Price (1 year)</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.history}>
              <CartesianGrid stroke="#1e293b" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={24} />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 11 }}
                domain={["auto", "auto"]}
                tickFormatter={(value: number) => num(value, 0)}
              />
              <Tooltip
                contentStyle={{ background: "#121826", border: "1px solid #1e293b", color: "#e2e8f0" }}
                formatter={(value) => [num(Number(value)), "Close"]}
              />
              <Line type="monotone" dataKey="close" stroke="#34d399" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="border border-slate-800">
          <div className="border-b border-slate-800 px-4 py-3 text-sm uppercase tracking-wide text-slate-500">
            Recent returns
          </div>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(data.returns).map(([key, value]) => (
                <tr key={key} className="border-t border-slate-800">
                  <td className="px-4 py-2 text-slate-400">{key}</td>
                  <td className={`px-4 py-2 text-right font-mono ${signedClass(value)}`}>{pct(value)}</td>
                </tr>
              ))}
              <tr className="border-t border-slate-800">
                <td className="px-4 py-2 text-slate-400">volume</td>
                <td className="px-4 py-2 text-right font-mono">{compact(data.volume)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="border border-slate-800">
          <div className="border-b border-slate-800 px-4 py-3 text-sm uppercase tracking-wide text-slate-500">
            Important features
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="px-4 py-2 font-medium">Feature</th>
                <th className="px-4 py-2 font-medium">Value</th>
                <th className="px-4 py-2 font-medium">Contribution</th>
              </tr>
            </thead>
            <tbody>
              {important.map((feature) => (
                <tr key={feature.key} className="border-t border-slate-800">
                  <td className="px-4 py-2 text-slate-300">{feature.label}</td>
                  <td className="px-4 py-2 font-mono text-slate-200">{formatFeature(feature.key, feature.value)}</td>
                  <td className={`px-4 py-2 font-mono ${signedClass(feature.contribution)}`}>
                    {num(feature.contribution, 3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function formatFeature(key: string, value: number | null): string {
  if (value === null) return "—";
  if (key === "rsi_14" || key === "rel_volume" || key === "log_dollar_volume") return num(value, 2);
  if (key.startsWith("days_")) return num(value, 0);
  return pct(value);
}
