"""HTML Email Templates for TradingView Alert Agent Reports."""

from datetime import datetime
from typing import List, Dict, Any, Optional
from jinja2 import Template


# Base HTML template with styling
BASE_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #0a0e1a;
            color: #e0e6ed;
            line-height: 1.6;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(135deg, #1a2332 0%, #0d1117 100%);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 24px;
            border: 1px solid #30363d;
        }
        
        .logo {
            font-size: 28px;
            font-weight: bold;
            color: #58a6ff;
            margin-bottom: 8px;
        }
        
        .logo-icon {
            display: inline-block;
            margin-right: 10px;
        }
        
        .report-type {
            font-size: 14px;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .report-date {
            font-size: 18px;
            color: #c9d1d9;
            margin-top: 8px;
        }
        
        .summary-card {
            background: #161b22;
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 20px;
            border: 1px solid #30363d;
        }
        
        .summary-title {
            font-size: 18px;
            font-weight: 600;
            color: #f0f6fc;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
        }
        
        .summary-title .icon {
            margin-right: 10px;
            font-size: 20px;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
        }
        
        .metric {
            background: #0d1117;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }
        
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #58a6ff;
        }
        
        .metric-label {
            font-size: 12px;
            color: #8b949e;
            margin-top: 4px;
        }
        
        .symbol-section {
            background: #161b22;
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 20px;
            border: 1px solid #30363d;
        }
        
        .symbol-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid #30363d;
        }
        
        .symbol-name {
            font-size: 22px;
            font-weight: bold;
            color: #f0f6fc;
        }
        
        .symbol-price {
            font-size: 20px;
            color: #58a6ff;
        }
        
        .pattern-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            margin-right: 8px;
            margin-bottom: 8px;
        }
        
        .pattern-bullish {
            background: rgba(35, 197, 94, 0.2);
            color: #23c55e;
            border: 1px solid rgba(35, 197, 94, 0.3);
        }
        
        .pattern-bearish {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .pattern-neutral {
            background: rgba(156, 163, 175, 0.2);
            color: #9ca3af;
            border: 1px solid rgba(156, 163, 175, 0.3);
        }
        
        .confidence-score {
            display: flex;
            align-items: center;
            margin-top: 12px;
        }
        
        .confidence-bar {
            flex: 1;
            height: 8px;
            background: #30363d;
            border-radius: 4px;
            margin: 0 12px;
            overflow: hidden;
        }
        
        .confidence-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        
        .confidence-high {
            background: linear-gradient(90deg, #23c55e, #16a34a);
        }
        
        .confidence-medium {
            background: linear-gradient(90deg, #f59e0b, #d97706);
        }
        
        .confidence-low {
            background: linear-gradient(90deg, #ef4444, #dc2626);
        }
        
        .ma20-status {
            display: flex;
            align-items: center;
            padding: 12px;
            background: #0d1117;
            border-radius: 8px;
            margin-top: 12px;
        }
        
        .ma20-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 12px;
        }
        
        .ma20-above {
            background: #23c55e;
            box-shadow: 0 0 8px rgba(35, 197, 94, 0.5);
        }
        
        .ma20-below {
            background: #ef4444;
            box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
        }
        
        .context-box {
            background: #0d1117;
            border-radius: 8px;
            padding: 16px;
            margin-top: 16px;
        }
        
        .context-title {
            font-size: 14px;
            font-weight: 600;
            color: #8b949e;
            margin-bottom: 8px;
        }
        
        .context-text {
            font-size: 14px;
            color: #c9d1d9;
            line-height: 1.5;
        }
        
        .recommendation {
            display: flex;
            align-items: center;
            padding: 16px;
            border-radius: 8px;
            margin-top: 16px;
            font-weight: 600;
        }
        
        .rec-strong-long {
            background: rgba(35, 197, 94, 0.15);
            border: 1px solid rgba(35, 197, 94, 0.3);
            color: #23c55e;
        }
        
        .rec-consider-long {
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.2);
            color: #4ade80;
        }
        
        .rec-neutral {
            background: rgba(156, 163, 175, 0.1);
            border: 1px solid rgba(156, 163, 175, 0.2);
            color: #9ca3af;
        }
        
        .rec-consider-short {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #f87171;
        }
        
        .rec-strong-short {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #ef4444;
        }
        
        .timeframe-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-top: 16px;
        }
        
        .timeframe-item {
            background: #0d1117;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }
        
        .timeframe-label {
            font-size: 12px;
            color: #8b949e;
            margin-bottom: 4px;
        }
        
        .timeframe-trend {
            font-size: 14px;
            font-weight: 600;
        }
        
        .trend-bullish {
            color: #23c55e;
        }
        
        .trend-bearish {
            color: #ef4444;
        }
        
        .trend-neutral {
            color: #9ca3af;
        }
        
        .alignment-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            margin-left: 6px;
        }
        
        .aligned {
            background: #23c55e;
        }
        
        .not-aligned {
            background: #ef4444;
        }
        
        .footer {
            text-align: center;
            padding: 24px;
            color: #6b7280;
            font-size: 12px;
            border-top: 1px solid #30363d;
            margin-top: 24px;
        }
        
        .footer a {
            color: #58a6ff;
            text-decoration: none;
        }
        
        .section-title {
            font-size: 16px;
            font-weight: 600;
            color: #f0f6fc;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #30363d;
        }
        
        .alert-list {
            list-style: none;
            padding: 0;
        }
        
        .alert-item {
            background: #0d1117;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .alert-time {
            font-size: 12px;
            color: #6b7280;
        }
        
        .no-data {
            text-align: center;
            padding: 40px;
            color: #6b7280;
        }
        
        @media (max-width: 600px) {
            .container {
                padding: 12px;
            }
            
            .timeframe-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .metric-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        {{ content }}
        
        <div class="footer">
            <p>TradingView Alert Agent &copy; {{ year }} | Automated Analysis Reports</p>
            <p>Generated at {{ generated_at }}</p>
        </div>
    </div>
</body>
</html>
"""


def get_report_header(report_type: str, report_date: str) -> str:
    """Generate report header HTML."""
    template = Template("""
        <div class="header">
            <div class="logo">
                <span class="logo-icon">📊</span>
                TradingView Alert Agent
            </div>
            <div class="report-type">{{ report_type }}</div>
            <div class="report-date">{{ report_date }}</div>
        </div>
    """)
    return template.render(report_type=report_type, report_date=report_date)


def get_summary_section(
    total_alerts: int,
    total_symbols: int,
    bullish_signals: int,
    bearish_signals: int,
    report_period: str
) -> str:
    """Generate summary metrics section."""
    template = Template("""
        <div class="summary-card">
            <div class="summary-title">
                <span class="icon">📈</span>
                Report Summary — {{ report_period }}
            </div>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-value">{{ total_alerts }}</div>
                    <div class="metric-label">Total Alerts</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{{ total_symbols }}</div>
                    <div class="metric-label">Symbols Active</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #23c55e;">{{ bullish_signals }}</div>
                    <div class="metric-label">Bullish Signals</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #ef4444;">{{ bearish_signals }}</div>
                    <div class="metric-label">Bearish Signals</div>
                </div>
            </div>
        </div>
    """)
    return template.render(
        total_alerts=total_alerts,
        total_symbols=total_symbols,
        bullish_signals=bullish_signals,
        bearish_signals=bearish_signals,
        report_period=report_period
    )


def get_symbol_analysis_section(
    symbol: str,
    price: float,
    patterns: List[Dict[str, Any]],
    ma20: Dict[str, Any],
    context: Dict[str, Any],
    multi_timeframe: Dict[str, Any]
) -> str:
    """Generate symbol analysis section HTML."""
    
    # Pattern badges
    pattern_badges = ""
    for pattern in patterns:
        pattern_type = pattern.get('type', '').replace('_', ' ').title()
        confidence = pattern.get('confidence', 0)
        direction = pattern.get('direction', 'neutral')
        
        if 'bullish' in pattern.get('type', ''):
            css_class = 'pattern-bullish'
        elif 'bearish' in pattern.get('type', ''):
            css_class = 'pattern-bearish'
        else:
            css_class = 'pattern-neutral'
        
        pattern_badges += f'<span class="pattern-badge {css_class}">{pattern_type} ({confidence:.0%})</span>'
    
    if not pattern_badges:
        pattern_badges = '<span class="pattern-badge pattern-neutral">No Patterns Detected</span>'
    
    # Confidence bar
    confidence = context.get('confidence', 0) if context else 0
    if confidence >= 0.75:
        confidence_class = 'confidence-high'
    elif confidence >= 0.50:
        confidence_class = 'confidence-medium'
    else:
        confidence_class = 'confidence-low'
    
    # MA20 status
    ma20_class = 'ma20-above' if ma20 and ma20.get('trend') == 'bullish' else 'ma20-below'
    ma20_text = f"Price ${ma20.get('price', 0):,.2f} is {'above' if ma20 and ma20.get('trend') == 'bullish' else 'below'} MA20 (${ma20.get('ma20', 0):,.2f})" if ma20 else "MA20 data unavailable"
    
    # Recommendation
    recommendation = context.get('recommendation', 'neutral') if context else 'neutral'
    rec_map = {
        'strong_long': ('rec-strong-long', 'Strong Long 📈'),
        'consider_long': ('rec-consider-long', 'Consider Long 📊'),
        'neutral': ('rec-neutral', 'Neutral ➖'),
        'consider_short': ('rec-consider-short', 'Consider Short 📉'),
        'strong_short': ('rec-strong-short', 'Strong Short 🔻'),
        'wait': ('rec-neutral', 'Wait ⏸️')
    }
    rec_class, rec_text = rec_map.get(recommendation, rec_map['neutral'])
    
    # Multi-timeframe
    tf_html = ""
    tf_order = [('weekly', '1W'), ('daily', '1D'), ('four_hour', '4H'), ('one_hour', '1H')]
    for tf_key, tf_label in tf_order:
        tf_data = multi_timeframe.get(tf_key, {}) if multi_timeframe else {}
        trend = tf_data.get('trend', 'neutral')
        aligned = tf_data.get('alignment', False)
        
        trend_class = f'trend-{trend}' if trend in ['bullish', 'bearish'] else 'trend-neutral'
        alignment_class = 'aligned' if aligned else 'not-aligned'
        
        tf_html += f"""
            <div class="timeframe-item">
                <div class="timeframe-label">{tf_label}</div>
                <div class="timeframe-trend {trend_class}">
                    {trend.title()}
                    <span class="alignment-indicator {alignment_class}"></span>
                </div>
            </div>
        """
    
    template = Template("""
        <div class="symbol-section">
            <div class="symbol-header">
                <div class="symbol-name">{{ symbol }}</div>
                <div class="symbol-price">${{ price:,.2f }}</div>
            </div>
            
            <div class="section-title">Detected Patterns</div>
            <div style="margin-bottom: 12px;">
                {{ pattern_badges }}
            </div>
            
            <div class="confidence-score">
                <span>Confidence:</span>
                <div class="confidence-bar">
                    <div class="confidence-fill {{ confidence_class }}" style="width: {{ confidence_pct }}%;"></div>
                </div>
                <span>{{ confidence_pct }}%</span>
            </div>
            
            <div class="ma20-status">
                <div class="ma20-indicator {{ ma20_class }}"></div>
                <span>{{ ma20_text }}</span>
            </div>
            
            <div class="context-box">
                <div class="context-title">Context Analysis</div>
                <div class="context-text">{{ context_reasoning }}</div>
            </div>
            
            <div class="recommendation {{ rec_class }}">
                <span style="font-size: 18px; margin-right: 10px;">💡</span>
                <span>Recommendation: {{ rec_text }}</span>
            </div>
            
            <div class="section-title" style="margin-top: 20px;">Multi-Timeframe Alignment</div>
            <div class="timeframe-grid">
                {{ timeframe_html }}
            </div>
        </div>
    """)
    
    return template.render(
        symbol=symbol,
        price=price,
        pattern_badges=pattern_badges,
        confidence_class=confidence_class,
        confidence_pct=int(confidence * 100),
        ma20_class=ma20_class,
        ma20_text=ma20_text,
        context_reasoning=context.get('reasoning', 'No context analysis available') if context else 'No context analysis available',
        rec_class=rec_class,
        rec_text=rec_text,
        timeframe_html=tf_html
    )


def get_recent_alerts_section(alerts: List[Dict[str, Any]]) -> str:
    """Generate recent alerts section HTML."""
    if not alerts:
        return """
            <div class="summary-card">
                <div class="section-title">Recent Alerts</div>
                <div class="no-data">No alerts in this period</div>
            </div>
        """
    
    alert_items = ""
    for alert in alerts[:10]:  # Show max 10
        symbol = alert.get('symbol', 'Unknown')
        message = alert.get('message', 'No message')
        time = alert.get('received_at', 'Unknown')
        
        alert_items += f"""
            <li class="alert-item">
                <div>
                    <strong>{symbol}</strong> — {message}
                </div>
                <div class="alert-time">{time}</div>
            </li>
        """
    
    template = Template("""
        <div class="summary-card">
            <div class="section-title">Recent Alerts</div>
            <ul class="alert-list">
                {{ alert_items }}
            </ul>
        </div>
    """)
    
    return template.render(alert_items=alert_items)


def render_full_report(
    report_type: str,
    report_date: str,
    year: int,
    generated_at: str,
    summary_data: Dict[str, Any],
    symbol_analyses: List[Dict[str, Any]],
    recent_alerts: List[Dict[str, Any]]
) -> str:
    """Render complete HTML report."""
    
    # Build content
    content = get_report_header(report_type, report_date)
    
    content += get_summary_section(
        total_alerts=summary_data.get('total_alerts', 0),
        total_symbols=summary_data.get('total_symbols', 0),
        bullish_signals=summary_data.get('bullish_signals', 0),
        bearish_signals=summary_data.get('bearish_signals', 0),
        report_period=summary_data.get('report_period', 'Unknown')
    )
    
    # Add symbol analyses
    for analysis in symbol_analyses:
        content += get_symbol_analysis_section(
            symbol=analysis.get('symbol', 'Unknown'),
            price=analysis.get('price', 0),
            patterns=analysis.get('patterns', []),
            ma20=analysis.get('ma20'),
            context=analysis.get('context'),
            multi_timeframe=analysis.get('multi_timeframe')
        )
    
    # Add recent alerts
    content += get_recent_alerts_section(recent_alerts)
    
    # Render full HTML
    base_template = Template(BASE_HTML_TEMPLATE)
    return base_template.render(
        report_title=f"{report_type} — TradingView Alert Agent",
        content=content,
        year=year,
        generated_at=generated_at
    )


def get_plain_text_version(
    report_type: str,
    report_date: str,
    summary_data: Dict[str, Any],
    symbol_analyses: List[Dict[str, Any]],
    recent_alerts: List[Dict[str, Any]]
) -> str:
    """Generate plain text fallback version of report."""
    
    lines = [
        f"{'=' * 60}",
        f"TradingView Alert Agent — {report_type}",
        f"{report_date}",
        f"{'=' * 60}",
        "",
        "SUMMARY",
        f"-" * 40,
        f"Report Period: {summary_data.get('report_period', 'Unknown')}",
        f"Total Alerts: {summary_data.get('total_alerts', 0)}",
        f"Symbols Active: {summary_data.get('total_symbols', 0)}",
        f"Bullish Signals: {summary_data.get('bullish_signals', 0)}",
        f"Bearish Signals: {summary_data.get('bearish_signals', 0)}",
        "",
    ]
    
    # Symbol analyses
    if symbol_analyses:
        lines.extend([
            "SYMBOL ANALYSES",
            f"-" * 40,
            ""
        ])
        
        for analysis in symbol_analyses:
            symbol = analysis.get('symbol', 'Unknown')
            price = analysis.get('price', 0)
            context = analysis.get('context', {})
            
            lines.extend([
                f"📊 {symbol} — ${price:,.2f}",
                f"   Confidence: {context.get('confidence', 0):.0%}",
                f"   Recommendation: {context.get('recommendation', 'neutral')}",
                f"   Context: {context.get('reasoning', 'N/A')[:100]}...",
                ""
            ])
    
    # Recent alerts
    if recent_alerts:
        lines.extend([
            "RECENT ALERTS",
            f"-" * 40,
            ""
        ])
        
        for alert in recent_alerts[:5]:
            lines.append(f"• {alert.get('symbol', 'Unknown')}: {alert.get('message', 'No message')}")
    
    lines.extend([
        "",
        f"{'=' * 60}",
        "Generated by TradingView Alert Agent",
        f"{'=' * 60}"
    ])
    
    return "\n".join(lines)


# Pre-defined report templates
DAILY_REPORT_TEMPLATE = "Daily Analysis Report"
WEEKLY_REPORT_TEMPLATE = "Weekly Analysis Report"
MONTHLY_REPORT_TEMPLATE = "Monthly Analysis Report"
