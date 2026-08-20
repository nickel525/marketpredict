import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import BacktestPage from "./pages/Backtest";
import RankingsPage from "./pages/Rankings";
import StockDetailPage from "./pages/StockDetail";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<RankingsPage />} />
        <Route path="/stocks/:ticker" element={<StockDetailPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
