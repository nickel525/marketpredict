from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.services import load_rankings, load_status, missing_artifact_detail

router = APIRouter()


@router.get("/rankings")
def get_rankings(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    try:
        return load_rankings(limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=missing_artifact_detail(exc)) from exc


@router.get("/status")
def get_status() -> dict:
    try:
        return load_status()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=missing_artifact_detail(exc)) from exc
