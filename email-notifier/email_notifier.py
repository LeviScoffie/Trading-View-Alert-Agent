"""Email Notifier - FastAPI service for TradingView Alert Agent.

Triggered by the external scheduler via HTTP POST.
No internal scheduling — the scheduler/ component owns timing.
"""

import logging
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from config import email_settings, app_settings
from templates import render_full_report, get_plain_text_version
from report_generator import ReportGenerator

logging.basicConfig(
    level=getattr(logging, app_settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Email Notifier",
    description="Generates and sends scheduled trading analysis reports",
    version="1.0.0"
)


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------

class EmailSender:
    """Handles email delivery via SMTP, SendGrid, or AWS SES."""

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

    def _send_via_smtp(self, subject, html_content, text_content, to_addr):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.email_from
        msg['To'] = to_addr
        msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        try:
            if self.smtp_tls:
                server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.email_from, to_addr, msg.as_string())
        finally:
            server.quit()

    def _send_via_sendgrid(self, subject, html_content, text_content, to_addr):
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail
        except ImportError:
            raise ImportError("SendGrid library not installed. Run: pip install sendgrid")
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
            raise Exception(f"SendGrid returned status {response.status_code}")

    def _send_via_ses(self, subject, html_content, text_content, to_addr):
        try:
            import boto3
        except ImportError:
            raise ImportError("Boto3 not installed. Run: pip install boto3")
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
            raise Exception(f"AWS SES returned status {response['ResponseMetadata']['HTTPStatusCode']}")


# ---------------------------------------------------------------------------
# Report generation + sending
# ---------------------------------------------------------------------------

class EmailNotifier:
    """Generates and sends analysis reports on demand."""

    def __init__(self):
        self.email_sender = EmailSender()
        self.report_generator = ReportGenerator()

    def generate_and_send_report(
        self,
        report_type: str,
        report_date: Optional[datetime] = None
    ) -> bool:
        logger.info(f"Generating {report_type} report...")

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

        symbol_analyses = self._generate_symbol_analyses(report_data['top_symbols'])

        html_content = render_full_report(
            report_type=f"{report_data['report_type']} Report",
            report_date=report_data['report_period'],
            year=datetime.now().year,
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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

        success = self.email_sender.send_email(subject, html_content, text_content)
        if success:
            logger.info(f"{report_type.capitalize()} report sent successfully")
        else:
            logger.error(f"Failed to send {report_type} report")
        return success

    def send_alert_email(self, symbol: str, analysis_result: dict) -> bool:
        """Send an immediate high-confidence alert email.

        Called by the Integration Service when confidence >= threshold.
        Uses a compact inline template rather than the full scheduled report.
        """
        context = analysis_result.get("context") or {}
        confidence = float(context.get("confidence", 0))
        recommendation = str(context.get("recommendation", "neutral")).replace("_", " ").title()
        reasoning = context.get("reasoning", "No reasoning provided.")

        patterns = analysis_result.get("patterns") or []
        pattern_list = ", ".join(p.get("type", "").replace("_", " ").title() for p in patterns) or "None detected"

        ma20 = analysis_result.get("ma20") or {}
        trend = str(ma20.get("trend", "unknown")).title()
        distance_pct = ma20.get("distance_pct", 0)

        subject = f"[{recommendation}] {symbol} Alert — {confidence:.0%} Confidence"

        html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;background:#0a0e1a;color:#e0e6ed;padding:20px;">
  <div style="max-width:600px;margin:0 auto;background:#1a2332;border-radius:10px;padding:24px;border:1px solid #30363d;">
    <h2 style="color:#58a6ff;margin:0 0 4px 0;">TradingView Alert Agent</h2>
    <p style="color:#8b949e;font-size:12px;margin:0 0 20px 0;text-transform:uppercase;letter-spacing:1px;">Immediate Alert</p>
    <h1 style="font-size:28px;margin:0 0 8px 0;">{symbol}</h1>
    <p style="font-size:18px;color:#{'3fb950' if 'long' in recommendation.lower() or 'bull' in recommendation.lower() else 'f85149' if 'short' in recommendation.lower() or 'bear' in recommendation.lower() else '8b949e'};font-weight:bold;margin:0 0 20px 0;">{recommendation} &mdash; {confidence:.0%} Confidence</p>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
      <tr><td style="padding:8px;border-bottom:1px solid #30363d;color:#8b949e;width:40%;">Patterns</td><td style="padding:8px;border-bottom:1px solid #30363d;">{pattern_list}</td></tr>
      <tr><td style="padding:8px;border-bottom:1px solid #30363d;color:#8b949e;">MA20 Trend</td><td style="padding:8px;border-bottom:1px solid #30363d;">{trend} ({distance_pct:+.2f}% from MA20)</td></tr>
    </table>
    <div style="background:#0d1117;border-radius:6px;padding:14px;font-size:14px;line-height:1.6;color:#c9d1d9;">
      <strong style="color:#8b949e;">Reasoning:</strong><br>{reasoning}
    </div>
    <p style="color:#8b949e;font-size:11px;margin-top:20px;text-align:center;">Generated by TradingView Alert Agent</p>
  </div>
</body>
</html>"""

        text_content = (
            f"ALERT: {symbol} — {recommendation} ({confidence:.0%} confidence)\n\n"
            f"Patterns: {pattern_list}\n"
            f"MA20 Trend: {trend} ({distance_pct:+.2f}% from MA20)\n\n"
            f"Reasoning: {reasoning}\n"
        )

        return self.email_sender.send_email(subject, html_content, text_content)

    def _generate_symbol_analyses(self, symbols: list) -> list:
        analyses = []
        for symbol in symbols:
            try:
                analysis = self.report_generator.generate_symbol_analysis(symbol)
                analyses.append(analysis)
            except Exception as e:
                logger.warning(f"Failed to analyze {symbol}: {e}")
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


# ---------------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------------

notifier = EmailNotifier()


class ReportRequest(BaseModel):
    report_date: Optional[str] = None  # ISO date string e.g. "2024-04-08"


class SendAlertRequest(BaseModel):
    symbol: str
    analysis: dict
    priority: str = "high"


@app.get("/health")
def health():
    return {"status": "ok", "service": "email-notifier"}


@app.post("/send-alert")
def send_alert(req: SendAlertRequest):
    """Send an immediate alert email for a high-confidence signal.

    Called by the Integration Service when confidence >= threshold.
    """
    success = notifier.send_alert_email(req.symbol, req.analysis)
    return {"status": "sent" if success else "failed", "symbol": req.symbol}


@app.post("/reports/daily")
def trigger_daily(req: ReportRequest = ReportRequest()):
    report_date = datetime.fromisoformat(req.report_date) if req.report_date else None
    success = notifier.generate_and_send_report('daily', report_date)
    return {"success": success, "report_type": "daily"}


@app.post("/reports/weekly")
def trigger_weekly(req: ReportRequest = ReportRequest()):
    report_date = datetime.fromisoformat(req.report_date) if req.report_date else None
    success = notifier.generate_and_send_report('weekly', report_date)
    return {"success": success, "report_type": "weekly"}


@app.post("/reports/monthly")
def trigger_monthly(req: ReportRequest = ReportRequest()):
    report_date = datetime.fromisoformat(req.report_date) if req.report_date else None
    success = notifier.generate_and_send_report('monthly', report_date)
    return {"success": success, "report_type": "monthly"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        logger.info("Running in test mode — generating daily report")
        notifier.generate_and_send_report('daily')
    else:
        uvicorn.run(app, host="0.0.0.0", port=8002)
