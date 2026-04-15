"""
Analysis Engine API — FastAPI wrapper around AnalysisEngine library.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime

from models import Timeframe, AlertInput
from analysis_engine import AnalysisEngine

app = FastAPI(title="Analysis Engine", version="1.0.0")

engine = AnalysisEngine(db_path=os.getenv("OHLCV_DB_PATH", "/app/data/ohlcv.db"))


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/analyze/{symbol}")
async def analyze_symbol(symbol: str, timeframe: str = "1D"):
    try:
        result = engine.analyze_symbol(symbol, Timeframe(timeframe))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe '{timeframe}'. Valid: 1W, 1D, 4H, 1H")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/alert")
async def process_alert(alert: AlertInput):
    try:
        return engine.process_alert(alert)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OHLCVPayload(BaseModel):
    data: List[Dict]


@app.post("/ohlcv/{symbol}/{timeframe}")
async def store_ohlcv(symbol: str, timeframe: str, payload: OHLCVPayload):
    try:
        engine.store_ohlcv_data(symbol, Timeframe(timeframe), payload.data)
        return {"status": "stored", "count": len(payload.data)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe '{timeframe}'. Valid: 1W, 1D, 4H, 1H")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patterns/{symbol}/{timeframe}")
async def get_patterns(symbol: str, timeframe: str, n_candles: int = 5):
    try:
        patterns = engine.get_recent_patterns(symbol, Timeframe(timeframe), n_candles)
        return {"patterns": patterns}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe '{timeframe}'. Valid: 1W, 1D, 4H, 1H")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/support-resistance/{symbol}")
async def get_support_resistance(symbol: str, timeframe: str = "1D"):
    try:
        return engine.get_support_resistance(symbol, Timeframe(timeframe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/multi-timeframe/{symbol}")
async def get_multi_timeframe(symbol: str):
    try:
        return {"summary": engine.get_multi_timeframe_summary(symbol)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))