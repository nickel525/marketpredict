export type RankedStock = {
  rank: number;
  ticker: string;
  name: string;
  probability: number;
  price: number;
  momentum: number | null;
  ret_5d: number | null;
  volume: number | null;
  rel_volume: number | null;
  sector: string;
  market_cap: number | null;
};

export type RankingsResponse = {
  as_of: string;
  collected_at: string | null;
  scored_at: string | null;
  positive_rate: number | null;
  ranking_metrics: Record<string, number>;
  stocks: RankedStock[];
};

export type FeatureRow = {
  key: string;
  label: string;
  value: number | null;
  contribution: number | null;
};

export type StockDetail = {
  ticker: string;
  name: string;
  sector: string;
  as_of: string;
  probability: number;
  price: number;
  volume: number | null;
  returns: Record<string, number | null>;
  features: FeatureRow[];
  explanation: string;
  history: { date: string; open: number; high: number; low: number; close: number; volume: number }[];
};

export type BacktestMetrics = {
  cagr: number;
  sharpe: number;
  max_drawdown: number;
  hit_rate: number;
  avg_weekly_return: number;
  pct_weeks_ge_5pct: number;
};

export type BacktestResponse = {
  config: {
    top_k: number;
    hold_days: number;
    cost_bps_per_side: number;
    n_weeks: number;
    start: string;
    end: string;
  };
  model: Record<string, number>;
  strategy: BacktestMetrics;
  strategy_net: BacktestMetrics;
  spy: BacktestMetrics;
  random: BacktestMetrics;
  equity_curve: {
    date: string;
    strategy: number;
    strategy_net: number;
    spy: number;
    random: number;
  }[];
  weeks: {
    date: string;
    tickers: string[];
    gross_return: number;
    net_return: number;
    spy_return: number | null;
    random_return: number;
    hit_5pct: boolean;
  }[];
};
