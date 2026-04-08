"""Orchestrator - Core flow: webhook → analysis → email."""

import logging
from typing import Optional

from config import settings
from models import (
    TradingViewAlert,
    AnalysisResult,
    ProcessAlertResponse,
    ContextInfo
)
from clients import webhook_client, analysis_client, email_client

logger = logging.getLogger(__name__)


class AlertOrchestrator:
    """Orchestrates the alert processing flow across services."""
    
    def __init__(self):
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD
    
    async def process_alert(self, alert: TradingViewAlert) -> ProcessAlertResponse:
        """
        Process an alert through the complete flow:
        1. Store alert in webhook receiver
        2. Trigger analysis
        3. Check confidence threshold
        4. Send email if confidence is high
        
        Args:
            alert: The TradingView alert to process
            
        Returns:
            ProcessAlertResponse with full processing results
        """
        logger.info(f"Starting alert processing for {alert.symbol}")
        
        # Step 1: Store alert in webhook receiver
        webhook_response = await webhook_client.store_alert(alert)
        
        if not webhook_response:
            logger.error(f"Failed to store alert for {alert.symbol}")
            return ProcessAlertResponse(
                alert_id=-1,
                symbol=alert.symbol,
                status="failed",
                message="Failed to store alert in webhook receiver"
            )
        
        alert_id = webhook_response.alert_id
        logger.info(f"Alert {alert_id} stored successfully")
        
        # Step 2: Trigger analysis
        analysis = await analysis_client.analyze(alert.symbol, alert.timeframe or "1D")
        
        if not analysis:
            logger.error(f"Failed to get analysis for {alert.symbol}")
            return ProcessAlertResponse(
                alert_id=alert_id,
                symbol=alert.symbol,
                status="analysis_failed",
                message="Failed to get analysis from analysis engine"
            )
        
        logger.info(f"Analysis completed for {alert.symbol}")
        
        # Step 3: Check confidence and send email if threshold met
        confidence = 0.0
        email_sent = False
        
        if analysis.context:
            confidence = analysis.context.confidence
            logger.info(f"Analysis confidence for {alert.symbol}: {confidence:.2f}")
            
            if confidence >= self.confidence_threshold:
                # Step 4: Send immediate email
                email_sent = await email_client.send_immediate_alert(
                    symbol=alert.symbol,
                    analysis=analysis
                )
                
                if email_sent:
                    logger.info(f"Immediate email sent for {alert.symbol} (confidence: {confidence:.2f})")
                else:
                    logger.warning(f"Failed to send email for {alert.symbol}")
            else:
                logger.info(f"Confidence {confidence:.2f} below threshold {self.confidence_threshold}, no email sent")
        else:
            logger.warning(f"No context in analysis for {alert.symbol}")
        
        # Determine final status
        status = "processed"
        if email_sent:
            status = "processed_with_email"
        elif confidence >= self.confidence_threshold:
            status = "processed_email_failed"
        
        return ProcessAlertResponse(
            alert_id=alert_id,
            symbol=alert.symbol,
            status=status,
            analysis=analysis,
            email_sent=email_sent,
            confidence=confidence,
            message=f"Alert processed. Confidence: {confidence:.2f}, Email sent: {email_sent}"
        )
    
    async def process_alert_simple(
        self,
        symbol: str,
        price: Optional[float] = None,
        message: Optional[str] = None,
        timeframe: str = "1D"
    ) -> ProcessAlertResponse:
        """
        Process an alert with simple parameters.
        
        Args:
            symbol: Trading symbol
            price: Optional price
            message: Optional message
            timeframe: Timeframe for analysis
            
        Returns:
            ProcessAlertResponse with full processing results
        """
        alert = TradingViewAlert(
            symbol=symbol,
            price=price,
            message=message,
            timeframe=timeframe
        )
        return await self.process_alert(alert)
    
    async def get_alert_status(self, alert_id: int) -> Optional[dict]:
        """
        Get the status of a processed alert.
        
        Args:
            alert_id: The ID of the alert to check
            
        Returns:
            Dict with alert status or None if not found
        """
        alert = await webhook_client.get_alert(alert_id)
        
        if not alert:
            return None
        
        # Get analysis for the symbol
        symbol = alert.get("symbol", "")
        analysis = await analysis_client.get_analysis(symbol)
        
        return {
            "alert_id": alert_id,
            "symbol": symbol,
            "received_at": alert.get("received_at"),
            "processed": alert.get("processed", False),
            "analysis": analysis.model_dump() if analysis else None
        }


# Global orchestrator instance
orchestrator = AlertOrchestrator()
