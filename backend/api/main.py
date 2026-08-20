from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import backtest, rankings, stocks

app = FastAPI(
    title="MarketPredict",
    description="Rank U.S. stocks by P(5-day return >= 5%)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rankings.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
