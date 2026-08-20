from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.services import load_backtest, missing_artifact_detail

router = APIRouter()


@router.get("/backtest")
def get_backtest() -> dict:
    try:
        return load_backtest()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=missing_artifact_detail(exc)) from exc
