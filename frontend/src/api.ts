import type { BacktestResponse, RankingsResponse, StockDetail } from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  rankings: (limit = 50) => getJson<RankingsResponse>(`/api/rankings?limit=${limit}`),
  stock: (ticker: string) => getJson<StockDetail>(`/api/stocks/${encodeURIComponent(ticker)}`),
  backtest: () => getJson<BacktestResponse>("/api/backtest"),
};
