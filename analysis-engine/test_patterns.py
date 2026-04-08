"""
Unit tests for candlestick pattern detection.
Tests all pattern types with synthetic and real-like data.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from models import PatternType, Timeframe
from pattern_detector import PatternDetector


class TestPatternDetector(unittest.TestCase):
    """Test cases for pattern detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = PatternDetector()
        self.timeframe = Timeframe.DAILY
    
    def _create_dataframe(self, candles):
        """Create a DataFrame from candle data."""
        base_time = datetime(2026, 4, 1)
        
        data = []
        for i, candle in enumerate(candles):
            data.append({
                'timestamp': base_time + timedelta(days=i),
                'open': candle[0],
                'high': candle[1],
                'low': candle[2],
                'close': candle[3],
                'volume': candle[4] if len(candle) > 4 else 1000
            })
        
        return pd.DataFrame(data)
    
    # === Engulfing Pattern Tests ===
    
    def test_bullish_engulfing(self):
        """Test bullish engulfing detection."""
        # Previous red candle, then green candle that engulfs it
        candles = [
            [100, 102, 98, 99, 1000],   # Red: open 100, close 99
            [98.5, 103, 98, 101, 1500], # Green: open 98.5, close 101 (engulfs)
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        bullish_engulfing = [p for p in patterns if p.type == PatternType.BULLISH_ENGULFING]
        self.assertEqual(len(bullish_engulfing), 1)
        self.assertGreater(bullish_engulfing[0].confidence, 0.7)
    
    def test_bearish_engulfing(self):
        """Test bearish engulfing detection."""
        # Previous green candle, then red candle that engulfs it
        candles = [
            [100, 102, 99, 101, 1000],  # Green: open 100, close 101
            [101.5, 102, 97, 98, 1500], # Red: open 101.5, close 98 (engulfs)
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        bearish_engulfing = [p for p in patterns if p.type == PatternType.BEARISH_ENGULFING]
        self.assertEqual(len(bearish_engulfing), 1)
        self.assertGreater(bearish_engulfing[0].confidence, 0.7)
    
    # === Doji Pattern Tests ===
    
    def test_standard_doji(self):
        """Test standard doji detection."""
        # Small body, similar open/close
        candles = [
            [100, 105, 95, 100.2, 1000],  # Small body, larger range
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        dojis = [p for p in patterns if p.type == PatternType.DOJI]
        self.assertGreaterEqual(len(dojis), 1)
    
    def test_dragonfly_doji(self):
        """Test dragonfly doji detection."""
        # Long lower shadow, small body at top
        candles = [
            [100, 100.5, 90, 100.2, 1000],  # Long lower shadow
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        dragonflies = [p for p in patterns if p.type == PatternType.DRAGONFLY_DOJI]
        self.assertGreaterEqual(len(dragonflies), 1)
    
    def test_gravestone_doji(self):
        """Test gravestone doji detection."""
        # Long upper shadow, small body at bottom
        candles = [
            [100, 110, 99.5, 99.8, 1000],  # Long upper shadow
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        gravestones = [p for p in patterns if p.type == PatternType.GRAVESTONE_DOJI]
        self.assertGreaterEqual(len(gravestones), 1)
    
    # === Hammer Pattern Tests ===
    
    def test_hammer(self):
        """Test hammer detection."""
        # Small body at top, long lower shadow
        candles = [
            [100, 100.5, 92, 100.3, 1000],  # Green hammer
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        hammers = [p for p in patterns if p.type == PatternType.HAMMER]
        self.assertGreaterEqual(len(hammers), 1)
    
    def test_inverted_hammer(self):
        """Test inverted hammer detection."""
        # Small body at bottom, long upper shadow
        candles = [
            [100, 108, 99.5, 100.2, 1000],  # Inverted hammer
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        inverted = [p for p in patterns if p.type == PatternType.INVERTED_HAMMER]
        self.assertGreaterEqual(len(inverted), 1)
    
    # === Star Pattern Tests ===
    
    def test_morning_star(self):
        """Test morning star detection."""
        # Red candle, small body star, green candle closing into first
        candles = [
            [105, 106, 100, 101, 1000],   # Red
            [100.5, 101.5, 99.5, 100.5, 800],  # Small star
            [100.8, 104, 100.5, 103.5, 1200],  # Green closing into first
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        morning_stars = [p for p in patterns if p.type == PatternType.MORNING_STAR]
        self.assertGreaterEqual(len(morning_stars), 1)
    
    def test_evening_star(self):
        """Test evening star detection."""
        # Green candle, small body star, red candle closing into first
        candles = [
            [100, 102, 99, 101, 1000],    # Green
            [101.5, 102.5, 100.5, 101.2, 800],  # Small star
            [100.8, 101, 97, 98, 1200],   # Red closing into first
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        evening_stars = [p for p in patterns if p.type == PatternType.EVENING_STAR]
        self.assertGreaterEqual(len(evening_stars), 1)
    
    # === Three Candle Pattern Tests ===
    
    def test_three_white_soldiers(self):
        """Test three white soldiers detection."""
        # Three consecutive green candles
        candles = [
            [100, 102, 99.5, 101, 1000],   # Green
            [100.8, 103, 100.5, 102.5, 1100],  # Green, opens in prev body
            [102, 105, 101.5, 104.5, 1200],    # Green, opens in prev body
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        soldiers = [p for p in patterns if p.type == PatternType.THREE_WHITE_SOLDIERS]
        self.assertEqual(len(soldiers), 1)
    
    def test_three_black_crows(self):
        """Test three black crows detection."""
        # Three consecutive red candles
        candles = [
            [105, 105.5, 102, 103, 1000],   # Red
            [103.5, 104, 100.5, 101, 1100],  # Red, opens in prev body
            [101.5, 102, 98.5, 99, 1200],    # Red, opens in prev body
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        crows = [p for p in patterns if p.type == PatternType.THREE_BLACK_CROWS]
        self.assertEqual(len(crows), 1)
    
    # === Edge Cases ===
    
    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        self.assertEqual(len(patterns), 0)
    
    def test_insufficient_data(self):
        """Test with insufficient data for patterns."""
        candles = [
            [100, 102, 99, 101, 1000],  # Only one candle
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        # Should detect single-candle patterns (doji, hammer) but not multi-candle
        self.assertLess(len(patterns), 3)  # At most doji/hammer variants
    
    def test_no_patterns_detected(self):
        """Test with data that has no clear patterns."""
        # Random-looking candles with no clear patterns
        candles = [
            [100, 103, 98, 101, 1000],
            [101, 104, 99, 102, 1000],
            [102, 105, 100, 103, 1000],
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        # May have some weak patterns, but nothing strong
        # This test mainly ensures no crashes
        self.assertIsInstance(patterns, list)
    
    def test_pattern_confidence_range(self):
        """Test that all pattern confidences are in valid range [0, 1]."""
        candles = [
            [100, 102, 98, 99, 1000],
            [98.5, 103, 98, 101, 1500],
            [101, 105, 100, 103, 1200],
            [103, 104, 99, 100, 1100],
            [100, 101, 96, 97, 1300],
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        for pattern in patterns:
            self.assertGreaterEqual(pattern.confidence, 0.0)
            self.assertLessEqual(pattern.confidence, 1.0)
    
    def test_pattern_timestamp(self):
        """Test that patterns have valid timestamps."""
        candles = [
            [100, 102, 98, 99, 1000],
            [98.5, 103, 98, 101, 1500],
        ]
        
        df = self._create_dataframe(candles)
        patterns = self.detector.detect_all_patterns(df, self.timeframe)
        
        for pattern in patterns:
            self.assertIsInstance(pattern.timestamp, datetime)
            self.assertIsInstance(pattern.index, int)
            self.assertGreaterEqual(pattern.index, 0)
    
    def test_get_recent_patterns(self):
        """Test getting recent patterns only."""
        # Create longer series with patterns at different points
        candles = [
            [100, 102, 98, 99, 1000],   # Day 1
            [98.5, 103, 98, 101, 1500], # Day 2 - bullish engulfing
            [101, 104, 100, 103, 1200], # Day 3
            [103, 104, 99, 100, 1100],  # Day 4
            [100, 101, 96, 97, 1300],   # Day 5
            [96.5, 100, 96, 99, 1400],  # Day 6 - potential pattern
        ]
        
        df = self._create_dataframe(candles)
        recent = self.detector.get_recent_patterns(df, self.timeframe, n=2)
        
        # Should only get patterns from last 2 candles
        for pattern in recent:
            self.assertGreaterEqual(pattern.index, len(df) - 2)


if __name__ == '__main__':
    unittest.main()