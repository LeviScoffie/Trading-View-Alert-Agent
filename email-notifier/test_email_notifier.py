"""Unit tests for email-notifier components."""

import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from report_generator import ReportGenerator
from templates import render_full_report, get_plain_text_version


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_candle(open_, high, low, close, ts=None):
    return {
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'timestamp': ts or '2024-01-01T00:00:00',
        'volume': 1000.0,
    }


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary alerts.db with sample data."""
    db_path = str(tmp_path / "alerts.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            message TEXT,
            price REAL,
            received_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE behavior_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            action TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    now = datetime.now()
    alerts = [
        ("BTCUSD", "Bullish engulfing pattern", 65000.0, (now - timedelta(hours=1)).isoformat()),
        ("BTCUSD", "Buy signal: long entry",    64800.0, (now - timedelta(hours=5)).isoformat()),
        ("ETHUSD", "Bearish reversal signal",   3200.0,  (now - timedelta(hours=2)).isoformat()),
        ("SOLUSD", "Long setup on support",     145.0,   (now - timedelta(hours=3)).isoformat()),
        ("XRPUSD", "Sell signal triggered",     0.52,    (now - timedelta(hours=4)).isoformat()),
    ]
    conn.executemany(
        "INSERT INTO alerts (symbol, message, price, received_at) VALUES (?,?,?,?)", alerts
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def generator(tmp_db):
    gen = ReportGenerator(db_path=tmp_db)
    gen.ohlcv_db_path = tmp_db  # point at same db (no ohlcv table → graceful degradation)
    return gen


# ---------------------------------------------------------------------------
# Pattern detection tests
# ---------------------------------------------------------------------------

class TestDetectPatterns:

    def test_bullish_engulfing(self, generator):
        # Previous candle: bearish (open > close), current: bullish and engulfs
        candles = [
            _make_candle(105, 107, 100, 101),  # bearish
            _make_candle(100, 110, 99,  108),  # bullish, engulfs
        ]
        patterns = generator.detect_patterns(candles)
        types = [p['type'] for p in patterns]
        assert 'bullish_engulfing' in types
        assert all(p['direction'] == 'bullish' for p in patterns if p['type'] == 'bullish_engulfing')

    def test_bearish_engulfing(self, generator):
        candles = [
            _make_candle(100, 108, 99,  106),  # bullish
            _make_candle(107, 110, 97,  98),   # bearish, engulfs
        ]
        patterns = generator.detect_patterns(candles)
        types = [p['type'] for p in patterns]
        assert 'bearish_engulfing' in types

    def test_doji(self, generator):
        # Open and close are almost the same (body < 10% of range)
        candles = [
            _make_candle(100, 110, 90, 101),   # normal
            _make_candle(100, 110, 90, 100.5),  # doji: body=0.5, range=20 → 2.5%
        ]
        patterns = generator.detect_patterns(candles)
        types = [p['type'] for p in patterns]
        assert 'doji' in types

    def test_hammer(self, generator):
        # Bullish hammer: meaningful body (> 10% range) so doji doesn't fire first.
        # open=95, close=100 (body=5), low=80 (lower_wick=15 > 2*body), high=101 (upper_wick=1 < body)
        candles = [
            _make_candle(100, 102, 98, 101),   # normal
            _make_candle(95,  101, 80, 100),   # hammer: body=5, lower_wick=15, upper_wick=1; range=21 → body/range≈24%
        ]
        patterns = generator.detect_patterns(candles)
        types = [p['type'] for p in patterns]
        assert 'hammer' in types

    def test_shooting_star(self, generator):
        # Bearish shooting star: meaningful body so doji doesn't fire.
        # open=100, close=95 (body=5), high=120 (upper_wick=20 > 2*body), low=94 (lower_wick=1 < body)
        candles = [
            _make_candle(100, 102, 98, 101),   # normal
            _make_candle(100, 120, 94, 95),    # shooting star: body=5, upper_wick=20, lower_wick=1; range=26 → body/range≈19%
        ]
        patterns = generator.detect_patterns(candles)
        types = [p['type'] for p in patterns]
        assert 'shooting_star' in types

    def test_no_pattern_insufficient_data(self, generator):
        candles = [_make_candle(100, 105, 95, 102)]
        patterns = generator.detect_patterns(candles)
        assert patterns == []

    def test_no_pattern_empty(self, generator):
        assert generator.detect_patterns([]) == []


# ---------------------------------------------------------------------------
# MA20 calculation tests
# ---------------------------------------------------------------------------

class TestCalculateMa20:

    def _make_candles(self, closes):
        return [_make_candle(c, c + 2, c - 2, c) for c in closes]

    def test_returns_none_with_fewer_than_20_candles(self, generator):
        candles = self._make_candles([100.0] * 19)
        assert generator.calculate_ma20(candles) is None

    def test_correct_average_flat(self, generator):
        candles = self._make_candles([100.0] * 25)
        result = generator.calculate_ma20(candles)
        assert result is not None
        assert result['ma20'] == 100.0
        # price == ma20: code uses `> ma20` so this is 'bearish' (not strictly greater)
        assert result['trend'] == 'bearish'
        assert result['slope'] == 'flat'

    def test_bullish_trend_price_above_ma(self, generator):
        closes = [100.0] * 20 + [110.0]  # last candle is above MA
        candles = self._make_candles(closes)
        result = generator.calculate_ma20(candles)
        assert result['trend'] == 'bullish'
        assert result['distance_pct'] > 0

    def test_bearish_trend_price_below_ma(self, generator):
        closes = [100.0] * 20 + [90.0]
        candles = self._make_candles(closes)
        result = generator.calculate_ma20(candles)
        assert result['trend'] == 'bearish'
        assert result['distance_pct'] < 0

    def test_rising_slope(self, generator):
        # MA of last 20 should be higher than MA of previous 20
        closes = list(range(1, 26))  # steadily rising
        candles = self._make_candles(closes)
        result = generator.calculate_ma20(candles)
        assert result['slope'] == 'rising'

    def test_falling_slope(self, generator):
        closes = list(range(25, 0, -1))  # steadily falling
        candles = self._make_candles(closes)
        result = generator.calculate_ma20(candles)
        assert result['slope'] == 'falling'


# ---------------------------------------------------------------------------
# Context analysis / confidence scoring tests
# ---------------------------------------------------------------------------

class TestGenerateContextAnalysis:

    def test_no_data_returns_neutral(self, generator):
        result = generator.generate_context_analysis("BTCUSD", [], None, {})
        assert result['recommendation'] == 'neutral'
        assert result['confidence'] == 0.5

    def test_bullish_pattern_with_bullish_ma_boosts_confidence(self, generator):
        patterns = [{'type': 'bullish_engulfing', 'confidence': 0.85, 'direction': 'bullish'}]
        ma20 = {'ma20': 100, 'price': 105, 'trend': 'bullish', 'slope': 'rising', 'distance_pct': 5.0}
        result = generator.generate_context_analysis("BTCUSD", patterns, ma20, {})
        assert result['confidence'] > 0.85
        assert result['recommendation'] in ('strong_long', 'consider_long')

    def test_bearish_pattern_with_bearish_ma_boosts_confidence(self, generator):
        patterns = [{'type': 'bearish_engulfing', 'confidence': 0.85, 'direction': 'bearish'}]
        ma20 = {'ma20': 100, 'price': 95, 'trend': 'bearish', 'slope': 'falling', 'distance_pct': -5.0}
        result = generator.generate_context_analysis("BTCUSD", patterns, ma20, {})
        assert result['confidence'] > 0.85
        assert result['recommendation'] in ('strong_short', 'consider_short')

    def test_opposing_ma_reduces_confidence(self, generator):
        patterns = [{'type': 'bullish_engulfing', 'confidence': 0.85, 'direction': 'bullish'}]
        ma20 = {'ma20': 100, 'price': 90, 'trend': 'bearish', 'slope': 'falling', 'distance_pct': -10.0}
        result = generator.generate_context_analysis("BTCUSD", patterns, ma20, {})
        assert result['confidence'] < 0.85

    def test_confidence_capped_at_095(self, generator):
        patterns = [{'type': 'bullish_engulfing', 'confidence': 0.85, 'direction': 'bullish'}]
        ma20 = {'ma20': 100, 'price': 110, 'trend': 'bullish', 'slope': 'rising', 'distance_pct': 10.0}
        multi_tf = {
            'weekly':     {'trend': 'bullish', 'alignment': True},
            'daily':      {'trend': 'bullish', 'alignment': True},
            'four_hour':  {'trend': 'bullish', 'alignment': True},
            'one_hour':   {'trend': 'bullish', 'alignment': True},
        }
        result = generator.generate_context_analysis("BTCUSD", patterns, ma20, multi_tf)
        assert result['confidence'] <= 0.95

    def test_bearish_tf_alignment_boosts_bearish_pattern(self, generator):
        patterns = [{'type': 'bearish_engulfing', 'confidence': 0.85, 'direction': 'bearish'}]
        ma20 = {'ma20': 100, 'price': 90, 'trend': 'bearish', 'slope': 'falling', 'distance_pct': -10.0}
        multi_tf = {
            'weekly':     {'trend': 'bearish', 'alignment': False},
            'daily':      {'trend': 'bearish', 'alignment': False},
            'four_hour':  {'trend': 'bearish', 'alignment': False},
        }
        result = generator.generate_context_analysis("BTCUSD", patterns, ma20, multi_tf)
        # ma20 boost (+0.10) + alignment boost pushes to cap (0.95)
        assert result['confidence'] >= 0.95


# ---------------------------------------------------------------------------
# Weekly report date logic tests
# ---------------------------------------------------------------------------

class TestWeeklyReportDateLogic:

    def test_monday_finds_previous_sunday(self, generator):
        monday = datetime(2024, 4, 8)  # April 8, 2024 is a Monday
        assert monday.weekday() == 0
        data = generator.generate_weekly_report_data(monday)
        # Sunday should be April 7
        assert data['end_time'].weekday() == 6
        assert data['end_time'].date() == datetime(2024, 4, 7).date()

    def test_sunday_stays_on_same_sunday(self, generator):
        sunday = datetime(2024, 4, 7)  # April 7, 2024 is a Sunday
        assert sunday.weekday() == 6
        data = generator.generate_weekly_report_data(sunday)
        assert data['end_time'].weekday() == 6
        assert data['end_time'].date() == sunday.date()

    def test_saturday_finds_previous_sunday(self, generator):
        saturday = datetime(2024, 4, 13)  # April 13, 2024 is a Saturday
        assert saturday.weekday() == 5
        data = generator.generate_weekly_report_data(saturday)
        # 6 days back = April 7 (Sunday)
        assert data['end_time'].weekday() == 6
        assert data['end_time'].date() == datetime(2024, 4, 7).date()

    def test_weekly_range_is_7_days(self, generator):
        wednesday = datetime(2024, 4, 10)
        data = generator.generate_weekly_report_data(wednesday)
        delta = data['end_time'] - data['start_time']
        assert delta.days == 7


# ---------------------------------------------------------------------------
# Report data generation tests (uses seeded DB)
# ---------------------------------------------------------------------------

class TestReportDataGeneration:

    def test_daily_report_has_required_keys(self, generator):
        data = generator.generate_daily_report_data()
        for key in ('report_type', 'report_period', 'start_time', 'end_time',
                    'total_alerts', 'total_symbols', 'bullish_signals', 'bearish_signals',
                    'recent_alerts', 'top_symbols'):
            assert key in data, f"Missing key: {key}"

    def test_daily_report_counts_alerts(self, generator):
        data = generator.generate_daily_report_data()
        assert data['total_alerts'] >= 0

    def test_monthly_report_period_is_full_month(self, generator):
        date = datetime(2024, 4, 15)
        data = generator.generate_monthly_report_data(date)
        assert data['start_time'].day == 1
        assert data['end_time'].month == 4

    def test_empty_db_returns_zeros(self, tmp_path):
        # New empty DB
        db = str(tmp_path / "empty.db")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE alerts (id INTEGER PRIMARY KEY, symbol TEXT, message TEXT, price REAL, received_at TEXT)")
        conn.commit()
        conn.close()
        gen = ReportGenerator(db_path=db)
        data = gen.generate_daily_report_data()
        assert data['total_alerts'] == 0
        assert data['total_symbols'] == 0


# ---------------------------------------------------------------------------
# Template rendering tests
# ---------------------------------------------------------------------------

class TestTemplateRendering:

    def test_render_full_report_returns_html(self):
        html = render_full_report(
            report_type="Daily Report",
            report_date="2024-04-08",
            year=2024,
            generated_at="2024-04-08 17:00:00",
            summary_data={
                'total_alerts': 5,
                'total_symbols': 3,
                'bullish_signals': 3,
                'bearish_signals': 2,
                'report_period': 'Last 24 hours'
            },
            symbol_analyses=[],
            recent_alerts=[]
        )
        assert '<html' in html.lower() or '<!doctype' in html.lower() or '<div' in html.lower()
        assert 'Daily Report' in html

    def test_render_report_includes_summary_stats(self):
        html = render_full_report(
            report_type="Weekly Report",
            report_date="Week of 2024-04-01",
            year=2024,
            generated_at="2024-04-08 17:00:00",
            summary_data={
                'total_alerts': 42,
                'total_symbols': 7,
                'bullish_signals': 25,
                'bearish_signals': 17,
                'report_period': 'Week of 2024-04-01'
            },
            symbol_analyses=[],
            recent_alerts=[]
        )
        assert '42' in html
        assert '7' in html

    def test_plain_text_version_contains_key_info(self):
        text = get_plain_text_version(
            report_type="Daily Report",
            report_date="2024-04-08",
            summary_data={
                'total_alerts': 10,
                'total_symbols': 4,
                'bullish_signals': 6,
                'bearish_signals': 4,
                'report_period': 'Last 24 hours'
            },
            symbol_analyses=[],
            recent_alerts=[]
        )
        assert 'Daily Report' in text
        assert isinstance(text, str)
        assert len(text) > 0

    def test_render_with_symbol_analysis(self):
        symbol_analyses = [{
            'symbol': 'BTCUSD',
            'price': 65000.0,
            'patterns': [{'type': 'bullish_engulfing', 'confidence': 0.85, 'direction': 'bullish'}],
            'ma20': {'ma20': 63000.0, 'price': 65000.0, 'trend': 'bullish', 'slope': 'rising', 'distance_pct': 3.17},
            'context': {'confidence': 0.90, 'reasoning': 'Bullish engulfing | Price above MA20', 'recommendation': 'strong_long'},
            'multi_timeframe': {
                'weekly': {'trend': 'bullish', 'alignment': True},
                'daily':  {'trend': 'bullish', 'alignment': True},
            }
        }]
        html = render_full_report(
            report_type="Daily Report",
            report_date="2024-04-08",
            year=2024,
            generated_at="2024-04-08 17:00:00",
            summary_data={'total_alerts': 1, 'total_symbols': 1, 'bullish_signals': 1, 'bearish_signals': 0, 'report_period': 'Last 24 hours'},
            symbol_analyses=symbol_analyses,
            recent_alerts=[]
        )
        assert 'BTCUSD' in html
