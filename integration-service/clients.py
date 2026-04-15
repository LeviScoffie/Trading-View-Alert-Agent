"""HTTP clients for communicating with other services."""

import logging
import hmac
import hashlib
import json
from typing import Optional, Dict, Any
import httpx

from config import settings
from models import (
    TradingViewAlert,
    AnalysisRequest,
    AnalysisResult,
    WebhookStoreResponse,
    EmailAlertRequest
)

logger = logging.getLogger(__name__)


def generate_webhook_signature(body: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload.
    
    Uses the same JSON serialization as httpx to ensure signature matches.
    """
    if not secret:
        return ""
    # httpx uses default json.dumps (no sort_keys, with separators)
    body_bytes = json.dumps(body).encode('utf-8')
    return hmac.new(
        secret.encode('utf-8'),
        body_bytes,
        hashlib.sha256
    ).hexdigest()


class BaseClient:
    """Base HTTP client with common functionality."""
    
    def __init__(self, base_url: str, service_name: str):
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.timeout = settings.REQUEST_TIMEOUT
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request with error handling."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"{self.service_name} HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"{self.service_name} request error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"{self.service_name} unexpected error: {str(e)}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        result = await self._request("GET", "/health")
        return result or {"status": "unhealthy"}


class WebhookClient(BaseClient):
    """Client for Webhook Receiver service."""
    
    def __init__(self):
        super().__init__(settings.WEBHOOK_RECEIVER_URL, "WebhookReceiver")
    
    async def store_alert(self, alert: TradingViewAlert) -> Optional[WebhookStoreResponse]:
        """Store alert in webhook receiver."""
        payload = alert.model_dump()
        signature = generate_webhook_signature(payload, settings.WEBHOOK_SECRET or "")
        headers = {}
        if signature:
            headers["X-TradingView-Signature"] = signature
        result = await self._request(
            "POST",
            "/webhook",
            json=payload,
            headers=headers
        )
        if result:
            return WebhookStoreResponse(**result)
        return None
    
    async def get_alert(self, alert_id: int) -> Optional[Dict[str, Any]]:
        """Get alert by ID."""
        # Webhook receiver doesn't have a direct GET endpoint for alerts by ID
        # We'll get recent alerts and filter
        result = await self._request("GET", f"/alerts")
        if result and "alerts" in result:
            for alert in result["alerts"]:
                if alert.get("id") == alert_id:
                    return alert
        return None
    
    async def get_alerts_by_symbol(self, symbol: str, limit: int = 100) -> Optional[Dict[str, Any]]:
        """Get alerts for a specific symbol."""
        return await self._request("GET", f"/alerts/{symbol}?limit={limit}")


class AnalysisClient(BaseClient):
    """Client for Analysis Engine service."""
    
    def __init__(self):
        super().__init__(settings.ANALYSIS_ENGINE_URL, "AnalysisEngine")
    
    async def analyze(self, symbol: str, timeframe: str = "1D") -> Optional[AnalysisResult]:
        """Trigger analysis for a symbol."""
        # Analysis engine needs a POST endpoint for analysis
        # For now, we'll assume it has an analyze endpoint
        result = await self._request(
            "POST",
            "/analyze",
            json={"symbol": symbol, "timeframe": timeframe}
        )
        if result:
            return AnalysisResult(**result)
        return None
    
    async def get_analysis(self, symbol: str, timeframe: str = "1D") -> Optional[AnalysisResult]:
        """Get analysis for a symbol (alternative to POST)."""
        result = await self._request(
            "GET",
            f"/analyze/{symbol}?timeframe={timeframe}"
        )
        if result:
            return AnalysisResult(**result)
        return None


class EmailClient(BaseClient):
    """Client for Email Notifier service."""
    
    def __init__(self):
        super().__init__(settings.EMAIL_NOTIFIER_URL, "EmailNotifier")
    
    async def send_immediate_alert(
        self,
        symbol: str,
        analysis: AnalysisResult,
        recipient: Optional[str] = None
    ) -> bool:
        """Send immediate email alert."""
        request_data = {
            "symbol": symbol,
            "analysis": analysis.model_dump(),
            "recipient": recipient
        }
        
        result = await self._request(
            "POST",
            "/send-alert",
            json=request_data
        )
        
        if result and result.get("status") == "sent":
            logger.info(f"Immediate alert email sent for {symbol}")
            return True
        
        logger.warning(f"Failed to send immediate alert email for {symbol}")
        return False
    
    async def send_alert_simple(self, symbol: str, confidence: float, reasoning: str) -> bool:
        """Send simple alert email."""
        result = await self._request(
            "POST",
            "/send-alert",
            json={
                "symbol": symbol,
                "confidence": confidence,
                "reasoning": reasoning
            }
        )
        
        return result is not None and result.get("status") == "sent"


class SchedulerClient(BaseClient):
    """Client for Scheduler service."""
    
    def __init__(self):
        super().__init__(settings.SCHEDULER_URL, "Scheduler")
    
    async def trigger_job(self, job_name: str) -> bool:
        """Trigger a scheduled job."""
        result = await self._request(
            "POST",
            f"/trigger/{job_name}"
        )
        return result is not None and result.get("status") == "triggered"


# Global client instances
webhook_client = WebhookClient()
analysis_client = AnalysisClient()
email_client = EmailClient()
scheduler_client = SchedulerClient()
