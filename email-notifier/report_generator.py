"""Report Generator - Query database and generate analysis reports."""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from contextlib import contextmanager

from config import database_settings, app_settings

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates analysis reports from database data."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize report generator."""
        self.db_path = db_path or database_settings.database_path
        self.ohlcv_db_path = database_settings.ohlcv_db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self) -> None:
        """Ensure database file exists."""
        db_file = Path(self.db_path)
        if not db_file.exists():
            project_root = Path(__file__).parent.parent
            alt_path = project_root / self.db_path
            if alt_path.exists():
                self.db_path = str(alt_path)
            else:
                logger.warning(f"Database not found at {self.db_path}")
    
    @contextmanager
    def _get_connection(self, db_path: Optional[str] = None):
        """Get database connection with row factory."""
        path = db_path or self.db_path
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get_alerts_for_period(
        self,
        start_time: datetime,
        end_time: datetime,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get alerts for a specific time period."""
        try:
            with self._get_connection() as conn:
                if symbol:
                    cursor = conn.execute(
                        """
                        SELECT * FROM alerts 
                        WHERE received_at >= ? AND received_at <= ?
                        AND symbol = ?
                        ORDER BY received_at DESC
                        """,
                        (start_time.isoformat(), end_time.isoformat(), symbol.upper())
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM alerts 
                        WHERE received_at >= ? AND received_at <= ?
                        ORDER BY received_at DESC
                        """,
                        (start_time.isoformat(), end_time.isoformat())
                    )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching alerts: {e}")
            return []
    
    def get_behavior_logs_for_period(
        self,
        start_time: datetime,
        end_time: datetime,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get behavior logs for a specific time period."""
        try:
            with self._get_connection() as conn:
                if symbol:
                    cursor = conn.execute(
                        """
                        SELECT * FROM behavior_logs 
                        WHERE timestamp >= ? AND timestamp <= ?
                        AND symbol = ?
                        ORDER BY timestamp DESC
                        """,
                        (start_time.isoformat(), end_time.isoformat(), symbol.upper())
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM behavior_logs 
                        WHERE timestamp >= ? AND timestamp <= ?
                        ORDER BY timestamp DESC
                        """,
                        (start_time.isoformat(), end_time.isoformat())
                    )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching behavior logs: {e}")
            return []
    
    def get_symbol_stats(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Get statistics for symbols in period."""
        try:
            with self._get_connection() as conn:
                total = conn.execute(
                    """
                    SELECT COUNT(*) FROM alerts 
                    WHERE received_at >= ? AND received_at <= ?
                    """,
                    (start_time.isoformat(), end_time.isoformat())
                ).fetchone()[0]
                
                symbols_result = conn.execute(
                    """
                    SELECT symbol, COUNT(*) as count 
                    FROM alerts 
                    WHERE received_at >= ? AND received_at <= ?
                    GROUP BY symbol
                    ORDER BY count DESC
                    """,
                    (start_time.isoformat(), end_time.isoformat())
                ).fetchall()
                
                symbols = [row['symbol'] for row in symbols_result]
                symbol_counts = {row['symbol']: row['count'] for row in symbols_result}
                
                bullish = 0
                bearish = 0
                for msg_row in conn.execute(
                    """
                    SELECT message FROM alerts 
                    WHERE received_at >= ? AND received_at <= ?
                    AND message IS NOT NULL
                    """,
                    (start_time.isoformat(), end_time.isoformat())
                ).fetchall():
                    msg = (msg_row['message'] or '').lower()
                    if any(w in msg for w in ['bullish', 'buy', 'long']):
                        bullish += 1
                    elif any(w in msg for w in ['bearish', 'sell', 'short']):
                        bearish += 1
                
                return {
                    'total_alerts': total,
                    'unique_symbols': symbols,
                    'symbol_counts': symbol_counts,
                    'bullish_signals': bullish,
                    'bearish_signals': bearish
                }
        except Exception as e:
            logger.error(f"Error fetching symbol stats: {e}")
            return {
                'total_alerts': 0,
                'unique_symbols': [],
                'symbol_counts': {},
                'bullish_signals': 0,
                'bearish_signals': 0
            }
    
    def generate_daily_report_data(self, report_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate data for daily report."""
        if report_date is None:
            report_date = datetime.now()
        
        end_time = report_date.replace(hour=17, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(days=1)
        
        stats = self.get_symbol_stats(start_time, end_time)
        alerts = self.get_alerts_for_period(start_time, end_time)
        
        return {
            'report_type': 'Daily',
            'report_period': f"Last 24 hours (ending {end_time.strftime('%Y-%m-%d %H:%M')})",
            'start_time': start_time,
            'end_time': end_time,
            'total_alerts': stats['total_alerts'],
            'total_symbols': len(stats['unique_symbols']),
            'bullish_signals': stats['bullish_signals'],
            'bearish_signals': stats['bearish_signals'],
            'recent_alerts': alerts[:10],
            'top_symbols': stats['unique_symbols'][:app_settings.top_symbols_limit]
        }
    
    def generate_weekly_report_data(self, report_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate data for weekly report (Sunday close)."""
        if report_date is None:
            report_date = datetime.now()
        
        # Find most recent Sunday
        days_since_sunday = report_date.weekday()
        if days_since_sunday != 6:  # 6 = Sunday
            days_since_sunday = (days_since_sunday + 1) % 7
        sunday = report_date - timedelta(days=days_since_sunday)
        
        end_time = sunday.replace(hour=17, minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(weeks=1)
        
        stats = self.get_symbol_stats(start_time, end_time)
        alerts = self.get_alerts_for_period(start_time, end_time)
        
        return {
            'report_type': 'Weekly',
            'report_period': f"Week of {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}",
            'start_time': start_time,
            'end_time': end_time,
            'total_alerts': stats['total_alerts'],
            'total_symbols': len(stats['unique_symbols']),
            'bullish_signals': stats['bullish_signals'],
            'bearish_signals': stats['bearish_signals'],
            'recent_alerts': alerts[:15],
            'top_symbols': stats['unique_symbols'][:app_settings.top_symbols_limit]
        }
    
    def generate_monthly_report_data(self, report_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate data for monthly report."""
        if report_date is None:
            report_date = datetime.now()
        
        # Last day of month
        if report_date.month == 12:
            end_time = report_date.replace(month=12, day=31, hour=17, minute=0, second=0, microsecond=0)
        else:
            next_month = report_date.replace(month=report_date.month + 1, day=1)
            end_time = (next_month - timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
        
        start_time = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        stats = self.get_symbol_stats(start_time, end_time)
        alerts = self.get_alerts_for_period(start_time, end_time)
        
        return {
            'report_type': 'Monthly',
            'report_period': end_time.strftime('%B %Y'),
            'start_time': start_time,
            'end_time': end_time,
            'total_alerts': stats['total_alerts'],
            'total_symbols': len(stats['unique_symbols']),
            'bullish_signals': stats['bullish_signals'],
            'bearish_signals': stats['bearish_signals'],
            'recent_alerts': alerts[:20],
            'top_symbols': stats['unique_symbols'][:app_settings.top_symbols_limit]
        }
    
    def get_top_symbols_for_period(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[str]:
        """Get top symbols by alert count for period."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT symbol, COUNT(*) as count 
                    FROM alerts 
                    WHERE received_at >= ? AND received_at <= ?
                    GROUP BY symbol
                    ORDER BY count DESC
                    LIMIT ?
                    """,
                    (start_time.isoformat(), end_time.isoformat(), limit)
                )
                return [row['symbol'] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching top symbols: {e}")
            return []

    def get_ohlcv_data(
        self,
        symbol: str,
        timeframe: str = '1d',
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Fetch OHLCV data for a symbol from the analysis engine database.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSD')
            timeframe: Candle timeframe (e.g., '1d', '4h', '1h')
            limit: Number of candles to fetch
            
        Returns:
            List of OHLCV candles
        """
        try:
            with self._get_connection(self.ohlcv_db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM ohlcv 
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (symbol.upper(), timeframe, limit)
                )
                rows = cursor.fetchall()
                # Reverse to get chronological order
                return [dict(row) for row in reversed(rows)]
        except Exception as e:
            logger.warning(f"Could not fetch OHLCV for {symbol}: {e}")
            return []

    def calculate_ma20(self, candles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Calculate 20-period moving average from candles.
        
        Args:
            candles: List of OHLCV candles (oldest first)
            
        Returns:
            MA20 analysis dict or None if insufficient data
        """
        if len(candles) < 20:
            return None
        
        # Use closing prices for MA calculation
        closes = [c['close'] for c in candles[-20:]]
        ma20 = sum(closes) / len(closes)
        
        current_price = candles[-1]['close']
        distance_pct = ((current_price - ma20) / ma20) * 100
        
        # Determine trend based on price vs MA
        trend = 'bullish' if current_price > ma20 else 'bearish'
        
        # Determine slope based on MA direction
        if len(candles) >= 21:
            prev_ma20 = sum([c['close'] for c in candles[-21:-1]]) / 20
            if ma20 > prev_ma20:
                slope = 'rising'
            elif ma20 < prev_ma20:
                slope = 'falling'
            else:
                slope = 'flat'
        else:
            slope = 'neutral'
        
        return {
            'price': current_price,
            'ma20': round(ma20, 2),
            'distance_pct': round(distance_pct, 2),
            'trend': trend,
            'slope': slope
        }

    def detect_patterns(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect candlestick patterns in recent candles.
        
        Args:
            candles: List of OHLCV candles (oldest first)
            
        Returns:
            List of detected patterns with confidence scores
        """
        patterns = []
        
        if len(candles) < 2:
            return patterns
        
        current = candles[-1]
        previous = candles[-2]
        
        # Helper functions
        def body_size(candle):
            return abs(candle['close'] - candle['open'])
        
        def is_bullish(candle):
            return candle['close'] > candle['open']
        
        def is_bearish(candle):
            return candle['close'] < candle['open']
        
        def total_range(candle):
            return candle['high'] - candle['low']
        
        # Bullish Engulfing
        if (is_bearish(previous) and is_bullish(current) and
            current['open'] < previous['close'] and
            current['close'] > previous['open'] and
            body_size(current) > body_size(previous)):
            patterns.append({
                'type': 'bullish_engulfing',
                'confidence': 0.85,
                'direction': 'bullish'
            })
        
        # Bearish Engulfing
        elif (is_bullish(previous) and is_bearish(current) and
              current['open'] > previous['close'] and
              current['close'] < previous['open'] and
              body_size(current) > body_size(previous)):
            patterns.append({
                'type': 'bearish_engulfing',
                'confidence': 0.85,
                'direction': 'bearish'
            })
        
        # Doji (small body)
        body = body_size(current)
        range_size = total_range(current)
        if range_size > 0 and body / range_size < 0.1:
            patterns.append({
                'type': 'doji',
                'confidence': 0.70,
                'direction': 'neutral'
            })
        
        # Hammer (small body at top, long lower wick)
        if is_bullish(current):
            lower_wick = current['open'] - current['low']
            upper_wick = current['high'] - current['close']
            if lower_wick > 2 * body and upper_wick < body:
                patterns.append({
                    'type': 'hammer',
                    'confidence': 0.80,
                    'direction': 'bullish'
                })
        
        # Shooting Star (small body at bottom, long upper wick)
        if is_bearish(current):
            upper_wick = current['high'] - current['open']
            lower_wick = current['close'] - current['low']
            if upper_wick > 2 * body and lower_wick < body:
                patterns.append({
                    'type': 'shooting_star',
                    'confidence': 0.75,
                    'direction': 'bearish'
                })
        
        return patterns

    def analyze_multi_timeframe(
        self,
        symbol: str,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Analyze symbol across multiple timeframes.
        
        Args:
            symbol: Trading symbol
            end_time: End time for analysis
            
        Returns:
            Multi-timeframe analysis dict
        """
        result = {}
        
        # Define timeframes to analyze
        timeframes = [
            ('1w', 'weekly'),
            ('1d', 'daily'),
            ('4h', 'four_hour'),
            ('1h', 'one_hour')
        ]
        
        for tf_code, tf_name in timeframes:
            candles = self.get_ohlcv_data(symbol, tf_code, limit=25)
            if candles:
                ma20 = self.calculate_ma20(candles)
                patterns = self.detect_patterns(candles)
                
                trend = ma20['trend'] if ma20 else 'neutral'
                
                result[tf_name] = {
                    'trend': trend,
                    'alignment': trend == 'bullish',
                    'ma20': ma20,
                    'patterns': patterns
                }
            else:
                result[tf_name] = {
                    'trend': 'unknown',
                    'alignment': False,
                    'ma20': None,
                    'patterns': []
                }
        
        return result

    def generate_context_analysis(
        self,
        symbol: str,
        patterns: List[Dict[str, Any]],
        ma20: Optional[Dict[str, Any]],
        multi_tf: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate context analysis and recommendation.
        
        Args:
            symbol: Trading symbol
            patterns: Detected patterns
            ma20: MA20 analysis
            multi_tf: Multi-timeframe analysis
            
        Returns:
            Context dict with confidence, reasoning, and recommendation
        """
        if not patterns and not ma20:
            return {
                'confidence': 0.5,
                'reasoning': 'Insufficient data for analysis',
                'recommendation': 'neutral'
            }
        
        # Calculate base confidence from patterns
        pattern_confidence = 0.5
        if patterns:
            pattern_confidence = max(p['confidence'] for p in patterns)
        
        # Adjust based on MA20 alignment
        ma20_boost = 0.0
        if ma20:
            has_bullish_pattern = any(p['direction'] == 'bullish' for p in patterns)
            has_bearish_pattern = any(p['direction'] == 'bearish' for p in patterns)
            
            if ma20['trend'] == 'bullish' and has_bullish_pattern:
                ma20_boost = 0.10
            elif ma20['trend'] == 'bearish' and has_bearish_pattern:
                ma20_boost = 0.10
            elif ma20['trend'] == 'bullish' and has_bearish_pattern:
                ma20_boost = -0.05
            elif ma20['trend'] == 'bearish' and has_bullish_pattern:
                ma20_boost = -0.05
        
        # Check multi-timeframe alignment
        tf_alignment = 0
        tf_count = 0
        for tf_name, tf_data in multi_tf.items():
            if tf_data.get('trend') in ['bullish', 'bearish']:
                tf_count += 1
                if tf_data.get('alignment'):
                    tf_alignment += 1
        
        alignment_boost = 0.0
        if tf_count >= 2:
            alignment_ratio = tf_alignment / tf_count
            alignment_boost = alignment_ratio * 0.10
        
        final_confidence = min(0.95, pattern_confidence + ma20_boost + alignment_boost)
        
        # Generate reasoning
        reasoning_parts = []
        if patterns:
            pattern_names = [p['type'].replace('_', ' ').title() for p in patterns[:2]]
            reasoning_parts.append(f"Detected: {', '.join(pattern_names)}")
        
        if ma20:
            ma_position = "above" if ma20['trend'] == 'bullish' else "below"
            reasoning_parts.append(f"Price {ma_position} MA20 ({ma20['distance_pct']:+.1f}%)")
        
        if tf_alignment >= 2:
            reasoning_parts.append(f"{tf_alignment} timeframes aligned")
        
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Neutral market conditions"
        
        # Generate recommendation
        if final_confidence >= 0.80:
            if any(p['direction'] == 'bullish' for p in patterns):
                recommendation = 'strong_long'
            elif any(p['direction'] == 'bearish' for p in patterns):
                recommendation = 'strong_short'
            else:
                recommendation = 'consider_long' if ma20 and ma20['trend'] == 'bullish' else 'neutral'
        elif final_confidence >= 0.65:
            if any(p['direction'] == 'bullish' for p in patterns):
                recommendation = 'consider_long'
            elif any(p['direction'] == 'bearish' for p in patterns):
                recommendation = 'consider_short'
            else:
                recommendation = 'neutral'
        elif final_confidence >= 0.50:
            recommendation = 'neutral'
        else:
            recommendation = 'wait'
        
        return {
            'confidence': round(final_confidence, 2),
            'reasoning': reasoning,
            'recommendation': recommendation
        }

    def generate_symbol_analysis(
        self,
        symbol: str,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate complete analysis for a symbol.
        
        Args:
            symbol: Trading symbol
            end_time: End time for analysis
            
        Returns:
            Complete symbol analysis dict
        """
        if end_time is None:
            end_time = datetime.now()
        
        # Fetch daily candles for primary analysis
        candles = self.get_ohlcv_data(symbol, '1d', limit=25)
        
        if not candles:
            logger.warning(f"No OHLCV data available for {symbol}")
            return {
                'symbol': symbol,
                'price': 0,
                'patterns': [],
                'ma20': None,
                'context': {
                    'confidence': 0.5,
                    'reasoning': 'No market data available',
                    'recommendation': 'neutral'
                },
                'multi_timeframe': {}
            }
        
        current_price = candles[-1]['close']
        
        # Run analyses
        patterns = self.detect_patterns(candles)
        ma20 = self.calculate_ma20(candles)
        multi_tf = self.analyze_multi_timeframe(symbol, end_time)
        context = self.generate_context_analysis(symbol, patterns, ma20, multi_tf)
        
        return {
            'symbol': symbol,
            'price': current_price,
            'patterns': patterns,
            'ma20': ma20,
            'context': context,
            'multi_timeframe': multi_tf
        }
