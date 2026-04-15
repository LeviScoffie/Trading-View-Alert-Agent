"""
Email Notifier API — FastAPI wrapper around EmailNotifier library.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from email_notifier import EmailNotifier

app = FastAPI(title="Email Notifier", version="1.0.0")

notifier = EmailNotifier()


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/report/daily")
async def send_daily_report(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(notifier.send_daily_report)
        return {"status": "queued", "report": "daily"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report/weekly")
async def send_weekly_report(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(notifier.send_weekly_report)
        return {"status": "queued", "report": "weekly"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report/monthly")
async def send_monthly_report(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(notifier.send_monthly_report)
        return {"status": "queued", "report": "monthly"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ReportRequest(BaseModel):
    symbols: Optional[List[str]] = None


@app.post("/report/send")
async def generate_and_send_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks
):
    try:
        background_tasks.add_task(notifier.generate_and_send_report)
        return {"status": "queued", "symbols": request.symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))