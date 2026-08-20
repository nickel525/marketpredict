import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import ErrorBanner from "../components/ErrorBanner";
import MetricCard from "../components/MetricCard";
import { compact, num, pct, signedClass } from "../format";
import type { RankingsResponse } from "../types";

export default function RankingsPage() {
  const [data, setData] = useState<RankingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .rankings(50)
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <ErrorBanner error={error} />;
  if (!data) return <div className="text-slate-400">Loading rankings…</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-medium text-white">Stocks Most Likely to Gain 5% This Week</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-400">
          Estimated probability that each stock rises 5% or more over the next 5 trading days.
          Prices as of {data.as_of}
          {data.collected_at ? ` · Yahoo pull ${formatStamp(data.collected_at)}` : ""}.
          Historical base rate in the training sample: {pct(data.positive_rate)}.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="Precision@5" value={pct(data.ranking_metrics.precision_at_5)} hint="Walk-forward OOS" />
        <MetricCard label="Precision@10" value={pct(data.ranking_metrics.precision_at_10)} hint="Walk-forward OOS" />
        <MetricCard label="Precision@20" value={pct(data.ranking_metrics.precision_at_20)} hint="Walk-forward OOS" />
      </div>

      <div className="overflow-x-auto border border-slate-800">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-ink-900 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Rank</th>
              <th className="px-4 py-3 font-medium">Ticker</th>
              <th className="px-4 py-3 font-medium">Probability</th>
              <th className="px-4 py-3 font-medium">Price</th>
              <th className="px-4 py-3 font-medium">Momentum</th>
              <th className="px-4 py-3 font-medium">Volume</th>
              <th className="px-4 py-3 font-medium">Sector</th>
            </tr>
          </thead>
          <tbody>
            {data.stocks.map((stock) => (
              <tr
                key={stock.ticker}
                className="cursor-pointer border-t border-slate-800 hover:bg-ink-800"
                onClick={() => navigate(`/stocks/${stock.ticker}`)}
              >
                <td className="px-4 py-3 font-mono text-slate-500">{stock.rank}</td>
                <td className="px-4 py-3">
                  <div className="font-medium text-white">{stock.ticker}</div>
                  <div className="text-xs text-slate-500">{stock.name}</div>
                </td>
                <td className="px-4 py-3 font-mono text-emerald-400">{pct(stock.probability)}</td>
                <td className="px-4 py-3 font-mono">{num(stock.price)}</td>
                <td className={`px-4 py-3 font-mono ${signedClass(stock.momentum)}`}>{pct(stock.momentum)}</td>
                <td className="px-4 py-3 font-mono">
                  {compact(stock.volume)}
                  {stock.rel_volume ? (
                    <span className="ml-2 text-xs text-slate-500">{num(stock.rel_volume, 1)}x</span>
                  ) : null}
                </td>
                <td className="px-4 py-3 text-slate-300">{stock.sector}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatStamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}
