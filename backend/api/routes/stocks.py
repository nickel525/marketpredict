from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.services import load_stock_detail, missing_artifact_detail

router = APIRouter()


@router.get("/stocks/{ticker}")
def get_stock(ticker: str) -> dict:
    try:
        return load_stock_detail(ticker)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=missing_artifact_detail(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
