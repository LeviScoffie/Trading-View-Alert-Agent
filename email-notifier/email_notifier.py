"""Email Notifier - Main scheduler and email sender for TradingView Alert Agent."""

import smtplib
import logging
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from config import email_settings, schedule_settings, app_settings
from templates import (
    render_full_report,
    get_plain_text_version,
    DAILY_REPORT_TEMPLATE,
    WEEKLY_REPORT_TEMPLATE,
    MONTHLY_REPORT_TEMPLATE
)
from report_generator import ReportGenerator

logger = logging.getLogger(__name__)


class EmailSender:
    """Handles email delivery via various providers."""
    
    def __init__(self):
        self.smtp_host = email_settings.smtp_host
        self.smtp_port = email_settings.smtp_port
        self.smtp_user = email_settings.smtp_user
        self.smtp_password = email_settings.smtp_password
        self.smtp_tls = email_settings.smtp_tls
        self.email_to = email_settings.email_to
        self.email_from = email_settings.email_from or email_settings.smtp_user
        self.provider = email_settings.email_provider
        self.max_retries = app_settings.max_retries
        self.retry_delay = app_settings.retry_delay_seconds
    
    def send_email(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        to_address: Optional[str] = None
    ) -> bool:
        """Send email with retry logic.
        
        Args:
            subject: Email subject
            html_content: HTML body
            text_content: Plain text fallback
            to_address: Override recipient (optional)
            
        Returns:
            True if sent successfully
        """
        to_addr = to_address or self.email_to
        
        if not to_addr:
            logger.error("No recipient email address configured")
            return False
        
        if not self.email_from:
            logger.error("No sender email address configured")
            return False
        
        for attempt in range(self.max_retries):
            try:
                if self.provider == "smtp":
                    self._send_via_smtp(subject, html_content, text_content, to_addr)
                elif self.provider == "sendgrid":
                    self._send_via_sendgrid(subject, html_content, text_content, to_addr)
                elif self.provider == "aws_ses":
                    self._send_via_ses(subject, html_content, text_content, to_addr)
                else:
                    logger.error(f"Unknown email provider: {self.provider}")
                    return False
                
                logger.info(f"Email sent successfully to {to_addr}")
                return True
                
            except Exception as e:
                logger.warning(f"Email send attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Email send failed after {self.max_retries} attempts")
                    return False
        
        return False
    
    def _send_via_smtp(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        to_addr: str
    ) -> None:
        """Send email via SMTP."""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.email_from
        msg['To'] = to_addr
        
        # Attach plain text and HTML versions
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # Connect and send
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        try:
            if self.smtp_tls:
                server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.email_from, to_addr, msg.as_string())
        finally:
            server.quit()
    
    def _send_via_sendgrid(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        to_addr: str
    ) -> None:
        """Send email via SendGrid."""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail
        except ImportError:
            raise ImportError("SendGrid library not installed. Install with: pip install sendgrid")
        
        if not email_settings.sendgrid_api_key:
            raise ValueError("SendGrid API key not configured")
        
        sg = sendgrid.SendGridAPIClient(api_key=email_settings.sendgrid_api_key)
        
        message = Mail(
            from_email=self.email_from,
            to_emails=to_addr,
            subject=subject,
            plain_text_content=text_content,
            html_content=html_content
        )
        
        response = sg.send(message)
        if response.status_code != 202:
            raise Exception(f"SendGrid returned status code: {response.status_code}")
    
    def _send_via_ses(
        self,
        subject: str,
        html_content: str,
        text_content: str,
        to_addr: str
    ) -> None:
        """Send email via AWS SES."""
        try:
            import boto3
        except ImportError:
            raise ImportError("Boto3 library not installed. Install with: pip install boto3")
        
        if not email_settings.aws_access_key_id or not email_settings.aws_secret_access_key:
            raise ValueError("AWS credentials not configured")
        
        client = boto3.client(
            'ses',
            region_name=email_settings.aws_region,
            aws_access_key_id=email_settings.aws_access_key_id,
            aws_secret_access_key=email_settings.aws_secret_access_key
        )
        
        response = client.send_email(
            Source=self.email_from,
            Destination={'ToAddresses': [to_addr]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': text_content},
                    'Html': {'Data': html_content}
                }
            }
        )
        
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise Exception(f"AWS SES returned status code: {response['ResponseMetadata']['HTTPStatusCode']}")


class EmailNotifier:
    """Main email notifier with scheduling capabilities."""
    
    def __init__(self):
        self.email_sender = EmailSender()
        self.report_generator = ReportGenerator()
        self.timezone = timezone(schedule_settings.timezone)
        self.scheduler: Optional[BlockingScheduler] = None
    
    def generate_and_send_report(
        self,
        report_type: str,
        report_date: Optional[datetime] = None
    ) -> bool:
        """Generate and send a report.
        
        Args:
            report_type: 'daily', 'weekly', or 'monthly'
            report_date: Report date (defaults to now)
            
        Returns:
            True if sent successfully
        """
        logger.info(f"Generating {report_type} report...")
        
        # Generate report data
        if report_type == 'daily':
            report_data = self.report_generator.generate_daily_report_data(report_date)
            subject = f"Daily Trading Analysis — {datetime.now().strftime('%Y-%m-%d')}"
        elif report_type == 'weekly':
            report_data = self.report_generator.generate_weekly_report_data(report_date)
            subject = f"Weekly Trading Analysis — Week of {report_data['start_time'].strftime('%Y-%m-%d')}"
        elif report_type == 'monthly':
            report_data = self.report_generator.generate_monthly_report_data(report_date)
            subject = f"Monthly Trading Analysis — {report_data['report_period']}"
        else:
            logger.error(f"Unknown report type: {report_type}")
            return False
        
        # Generate symbol analyses (placeholder - would integrate with analysis engine)
        symbol_analyses = self._generate_symbol_analyses(report_data['top_symbols'])
        
        # Render HTML and plain text
        html_content = render_full_report(
            report_type=f"{report_data['report_type']} Report",
            report_date=report_data['report_period'],
            year=datetime.now().year,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z'),
            summary_data={
                'total_alerts': report_data['total_alerts'],
                'total_symbols': report_data['total_symbols'],
                'bullish_signals': report_data['bullish_signals'],
                'bearish_signals': report_data['bearish_signals'],
                'report_period': report_data['report_period']
            },
            symbol_analyses=symbol_analyses,
            recent_alerts=report_data['recent_alerts']
        )
        
        text_content = get_plain_text_version(
            report_type=f"{report_data['report_type']} Report",
            report_date=report_data['report_period'],
            summary_data={
                'total_alerts': report_data['total_alerts'],
                'total_symbols': report_data['total_symbols'],
                'bullish_signals': report_data['bullish_signals'],
                'bearish_signals': report_data['bearish_signals'],
                'report_period': report_data['report_period']
            },
            symbol_analyses=symbol_analyses,
            recent_alerts=report_data['recent_alerts']
        )
        
        # Send email
        success = self.email_sender.send_email(subject, html_content, text_content)
        
        if success:
            logger.info(f"{report_type.capitalize()} report sent successfully")
        else:
            logger.error(f"Failed to send {report_type} report")
        
        return success
    
    def _generate_symbol_analyses(self, symbols: list) -> list:
        """Generate analysis for top symbols using real market data.
        
        Fetches OHLCV data and runs pattern detection, MA20 analysis,
        and context scoring for each symbol.
        """
        analyses = []
        for symbol in symbols:
            try:
                analysis = self.report_generator.generate_symbol_analysis(symbol)
                analyses.append(analysis)
                logger.debug(f"Generated analysis for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to analyze {symbol}: {e}")
                # Fallback to basic structure
                analyses.append({
                    'symbol': symbol,
                    'price': 0,
                    'patterns': [],
                    'ma20': None,
                    'context': {
                        'confidence': 0.5,
                        'reasoning': 'Analysis unavailable',
                        'recommendation': 'neutral'
                    },
                    'multi_timeframe': {}
                })
        return analyses
    
    def send_alert_email(self, symbol: str, analysis_result: dict) -> bool:
        """Send an immediate email for a single high-confidence alert.

        Called by alert_processor when confidence >= CONFIDENCE_THRESHOLD.
        Uses the same HTML template as scheduled reports but scoped to one symbol.

        Args:
            symbol:          Trading symbol, e.g. "BTCUSD".
            analysis_result: Full AnalysisResult serialised as a dict.

        Returns:
            True if the email was delivered successfully.
        """
        context        = analysis_result.get("context") or {}
        confidence     = float(context.get("confidence", 0))
        recommendation = str(context.get("recommendation", "neutral"))
        raw_data       = analysis_result.get("raw_data") or {}

        # Subject line with emoji direction cue
        direction_icon = "📈" if "long" in recommendation else "📉" if "short" in recommendation else "➖"
        subject = (
            f"{direction_icon} High-Confidence Signal: {symbol} — "
            f"{recommendation.replace('_', ' ').title()} ({confidence:.0%})"
        )

        # Build a single-symbol analysis block that matches the template schema
        patterns_raw = analysis_result.get("patterns") or []
        symbol_analysis = {
            "symbol":         symbol,
            "price":          raw_data.get("latest_price", 0),
            "patterns":       patterns_raw,
            "ma20":           analysis_result.get("ma20"),
            "context":        context,
            "multi_timeframe": analysis_result.get("multi_timeframe") or {},
        }

        html_content = render_full_report(
            report_type="Real-Time Alert",
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            year=datetime.now().year,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary_data={
                "total_alerts":    1,
                "total_symbols":   1,
                "bullish_signals": 1 if "long"  in recommendation else 0,
                "bearish_signals": 1 if "short" in recommendation else 0,
                "report_period":   "Real-Time Alert",
            },
            symbol_analyses=[symbol_analysis],
            recent_alerts=[],
        )

        text_content = (
            f"HIGH-CONFIDENCE ALERT\n"
            f"{'=' * 50}\n"
            f"Symbol:         {symbol}\n"
            f"Recommendation: {recommendation.replace('_', ' ').title()}\n"
            f"Confidence:     {confidence:.0%}\n"
            f"Context:        {context.get('reasoning', 'N/A')}\n"
            f"{'=' * 50}\n"
            f"Generated by TradingView Alert Agent"
        )

        logger.info("Sending alert email for %s (confidence=%.0f%%)", symbol, confidence * 100)
        return self.email_sender.send_email(subject, html_content, text_content)

    def send_daily_report(self) -> bool:
        """Send daily report."""
        return self.generate_and_send_report('daily')
    
    def send_weekly_report(self) -> bool:
        """Send weekly report."""
        return self.generate_and_send_report('weekly')
    
    def send_monthly_report(self) -> bool:
        """Send monthly report."""
        return self.generate_and_send_report('monthly')
    
    def start_scheduler(self) -> None:
        """Start the APScheduler for automated report delivery."""
        logger.info("Starting email notifier scheduler...")
        
        self.scheduler = BlockingScheduler(timezone=self.timezone)
        
        # Daily report at 5:00 PM EST
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(
                hour=schedule_settings.daily_report_hour,
                minute=schedule_settings.daily_report_minute,
                timezone=self.timezone
            ),
            id='daily_report',
            name='Daily Trading Analysis Report',
            replace_existing=True
        )
        logger.info(f"Scheduled daily report at {schedule_settings.daily_report_hour}:00 {self.timezone}")
        
        # Weekly report on Sunday at 5:00 PM EST
        self.scheduler.add_job(
            self.send_weekly_report,
            CronTrigger(
                day_of_week='sun',
                hour=schedule_settings.weekly_report_hour,
                minute=schedule_settings.weekly_report_minute,
                timezone=self.timezone
            ),
            id='weekly_report',
            name='Weekly Trading Analysis Report',
            replace_existing=True
        )
        logger.info(f"Scheduled weekly report on Sunday at {schedule_settings.weekly_report_hour}:00 {self.timezone}")
        
        # Monthly report on last day of month at 5:00 PM EST
        self.scheduler.add_job(
            self.send_monthly_report,
            CronTrigger(
                day='last',
                hour=schedule_settings.monthly_report_hour,
                minute=schedule_settings.monthly_report_minute,
                timezone=self.timezone
            ),
            id='monthly_report',
            name='Monthly Trading Analysis Report',
            replace_existing=True
        )
        logger.info(f"Scheduled monthly report on last day at {schedule_settings.monthly_report_hour}:00 {self.timezone}")
        
        logger.info("Scheduler started. Press Ctrl+C to exit.")
        self.scheduler.start()
    
    def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")


def main():
    """Main entry point."""
    logging.basicConfig(
        level=getattr(logging, app_settings.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    notifier = EmailNotifier()
    
    # Check if running in test mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        logger.info("Running in test mode - sending sample daily report")
        notifier.generate_and_send_report('daily')
    else:
        # Start scheduler
        notifier.start_scheduler()


if __name__ == '__main__':
    main()
