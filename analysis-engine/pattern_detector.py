"""
Candlestick Pattern Detector Module.
Implements detection algorithms for various candlestick patterns.
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from datetime import datetime

from models import Pattern, PatternType, Timeframe, Config


class PatternDetector:
    """
    Detects candlestick patterns in OHLCV data.
    
    Patterns implemented:
    - Engulfing (bullish/bearish)
    - Doji variants (standard, dragonfly, gravestone)
    - Hammer / Inverted Hammer
    - Morning Star / Evening Star
    - Three White Soldiers / Three Black Crows
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
    
    def detect_all_patterns(self, df: pd.DataFrame, timeframe: Timeframe) -> List[Pattern]:
        """
        Detect all patterns in the given DataFrame.
        
        Args:
            df: DataFrame with OHLCV columns
            timeframe: The timeframe of the data
        
        Returns:
            List of detected patterns
        """
        if len(df) == 0:
            return []

        patterns = []
        
        # Single candle patterns
        patterns.extend(self._detect_doji_patterns(df, timeframe))
        patterns.extend(self._detect_hammer_patterns(df, timeframe))
        
        # Two candle patterns
        patterns.extend(self._detect_engulfing_patterns(df, timeframe))
        
        # Three candle patterns
        patterns.extend(self._detect_star_patterns(df, timeframe))
        patterns.extend(self._detect_three_candle_patterns(df, timeframe))
        
        return patterns
    
    def _calculate_candle_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate candle body and shadow metrics."""
        df = df.copy()
        
        # Body calculations
        df['body'] = (df['close'] - df['open']).abs()
        df['body_pct'] = df['body'] / (df['high'] - df['low']).replace(0, np.nan)
        df['is_green'] = df['close'] > df['open']
        df['is_red'] = df['close'] < df['open']
        
        # Shadow calculations
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        df['range'] = df['high'] - df['low']
        
        # Avoid division by zero
        df['upper_shadow_pct'] = df['upper_shadow'] / df['range'].replace(0, np.nan)
        df['lower_shadow_pct'] = df['lower_shadow'] / df['range'].replace(0, np.nan)
        
        return df
    
    def _detect_doji_patterns(self, df: pd.DataFrame, timeframe: Timeframe) -> List[Pattern]:
        """Detect doji and doji variants."""
        patterns = []
        df = self._calculate_candle_metrics(df)
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Skip if range is zero (no price movement)
            if row['range'] == 0:
                continue
            
            # Standard Doji: small body relative to range
            if row['body_pct'] < self.config.doji_threshold:
                # Dragonfly Doji: long lower shadow, little/no upper shadow
                if (row['lower_shadow_pct'] > 0.6 and 
                    row['upper_shadow_pct'] < 0.1):
                    patterns.append(Pattern(
                        type=PatternType.DRAGONFLY_DOJI,
                        confidence=self._calculate_doji_confidence(row, 'dragonfly'),
                        timeframe=timeframe,
                        timestamp=row['timestamp'],
                        index=i
                    ))
                # Gravestone Doji: long upper shadow, little/no lower shadow
                elif (row['upper_shadow_pct'] > 0.6 and 
                      row['lower_shadow_pct'] < 0.1):
                    patterns.append(Pattern(
                        type=PatternType.GRAVESTONE_DOJI,
                        confidence=self._calculate_doji_confidence(row, 'gravestone'),
                        timeframe=timeframe,
                        timestamp=row['timestamp'],
                        index=i
                    ))
                # Standard Doji
                else:
                    patterns.append(Pattern(
                        type=PatternType.DOJI,
                        confidence=self._calculate_doji_confidence(row, 'standard'),
                        timeframe=timeframe,
                        timestamp=row['timestamp'],
                        index=i
                    ))
        
        return patterns
    
    def _detect_hammer_patterns(self, df: pd.DataFrame, timeframe: Timeframe) -> List[Pattern]:
        """Detect hammer and inverted hammer patterns."""
        patterns = []
        df = self._calculate_candle_metrics(df)
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            if row['range'] == 0:
                continue
            
            # Hammer: small body at top, long lower shadow, little upper shadow
            if (row['lower_shadow_pct'] > 0.6 and 
                row['upper_shadow_pct'] < 0.15 and
                row['body_pct'] < 0.3):
                
                # Bullish hammer (green)
                if row['is_green']:
                    patterns.append(Pattern(
                        type=PatternType.HAMMER,
                        confidence=self._calculate_hammer_confidence(row),
                        timeframe=timeframe,
                        timestamp=row['timestamp'],
                        index=i
                    ))
            
            # Inverted Hammer: small body at bottom, long upper shadow, little lower shadow
            if (row['upper_shadow_pct'] > 0.6 and 
                row['lower_shadow_pct'] < 0.15 and
                row['body_pct'] < 0.3):
                
                patterns.append(Pattern(
                    type=PatternType.INVERTED_HAMMER,
                    confidence=self._calculate_hammer_confidence(row),
                    timeframe=timeframe,
                    timestamp=row['timestamp'],
                    index=i
                ))
        
        return patterns
    
    def _detect_engulfing_patterns(self, df: pd.DataFrame, timeframe: Timeframe) -> List[Pattern]:
        """Detect bullish and bearish engulfing patterns."""
        patterns = []
        
        if len(df) < 2:
            return patterns
        
        df = self._calculate_candle_metrics(df)
        
        for i in range(1, len(df)):
            prev = df.iloc[i-1]
            curr = df.iloc[i]
            
            # Bullish Engulfing
            # Previous red candle, current green candle that engulfs previous body
            if (prev['is_red'] and curr['is_green'] and
                curr['open'] < prev['close'] and  # Current opens below previous close
                curr['close'] > prev['open']):     # Current closes above previous open
                
                confidence = self._calculate_engulfing_confidence(prev, curr, 'bullish')
                patterns.append(Pattern(
                    type=PatternType.BULLISH_ENGULFING,
                    confidence=confidence,
                    timeframe=timeframe,
                    timestamp=curr['timestamp'],
                    index=i
                ))
            
            # Bearish Engulfing
            # Previous green candle, current red candle that engulfs previous body
            if (prev['is_green'] and curr['is_red'] and
                curr['open'] > prev['close'] and  # Current opens above previous close
                curr['close'] < prev['open']):     # Current closes below previous open
                
                confidence = self._calculate_engulfing_confidence(prev, curr, 'bearish')
                patterns.append(Pattern(
                    type=PatternType.BEARISH_ENGULFING,
                    confidence=confidence,
                    timeframe=timeframe,
                    timestamp=curr['timestamp'],
                    index=i
                ))
        
        return patterns
    
    def _detect_star_patterns(self, df: pd.DataFrame, timeframe: Timeframe) -> List[Pattern]:
        """Detect morning star and evening star patterns."""
        patterns = []
        
        if len(df) < 3:
            return patterns
        
        df = self._calculate_candle_metrics(df)
        
        for i in range(2, len(df)):
            first = df.iloc[i-2]
            middle = df.iloc[i-1]
            last = df.iloc[i]
            
            # Morning Star (bullish reversal)
            # 1. First candle: strong red
            # 2. Middle candle: small body (star), gaps down
            # 3. Last candle: strong green, closes into first candle body
            if (first['is_red'] and first['body_pct'] > 0.3 and
                middle['body_pct'] < 0.3 and
                last['is_green'] and last['body_pct'] > 0.3 and
                last['close'] > (first['open'] + first['close']) / 2):
                
                confidence = self._calculate_star_confidence(first, middle, last, 'morning')
                patterns.append(Pattern(
                    type=PatternType.MORNING_STAR,
                    confidence=confidence,
                    timeframe=timeframe,
                    timestamp=last['timestamp'],
                    index=i
                ))
            
            # Evening Star (bearish reversal)
            # 1. First candle: strong green
            # 2. Middle candle: small body (star), gaps up
            # 3. Last candle: strong red, closes into first candle body
            if (first['is_green'] and first['body_pct'] > 0.3 and
                middle['body_pct'] < 0.3 and
                last['is_red'] and last['body_pct'] > 0.3 and
                last['close'] < (first['open'] + first['close']) / 2):
                
                confidence = self._calculate_star_confidence(first, middle, last, 'evening')
                patterns.append(Pattern(
                    type=PatternType.EVENING_STAR,
                    confidence=confidence,
                    timeframe=timeframe,
                    timestamp=last['timestamp'],
                    index=i
                ))
        
        return patterns
    
    def _detect_three_candle_patterns(self, df: pd.DataFrame, timeframe: Timeframe) -> List[Pattern]:
        """Detect three white soldiers and three black crows."""
        patterns = []
        
        if len(df) < 3:
            return patterns
        
        df = self._calculate_candle_metrics(df)
        
        for i in range(2, len(df)):
            c1 = df.iloc[i-2]
            c2 = df.iloc[i-1]
            c3 = df.iloc[i]
            
            # Three White Soldiers (strong bullish)
            # Three consecutive green candles with:
            # - Each opens within previous body
            # - Each closes higher
            # - Decent sized bodies
            if (c1['is_green'] and c2['is_green'] and c3['is_green'] and
                c1['body_pct'] > 0.3 and c2['body_pct'] > 0.3 and c3['body_pct'] > 0.3 and
                c2['open'] > c1['open'] and c2['open'] < c1['close'] and
                c3['open'] > c2['open'] and c3['open'] < c2['close'] and
                c2['close'] > c1['close'] and c3['close'] > c2['close']):
                
                confidence = self._calculate_three_candle_confidence(c1, c2, c3, 'soldiers')
                patterns.append(Pattern(
                    type=PatternType.THREE_WHITE_SOLDIERS,
                    confidence=confidence,
                    timeframe=timeframe,
                    timestamp=c3['timestamp'],
                    index=i
                ))
            
            # Three Black Crows (strong bearish)
            # Three consecutive red candles with:
            # - Each opens within previous body
            # - Each closes lower
            # - Decent sized bodies
            if (c1['is_red'] and c2['is_red'] and c3['is_red'] and
                c1['body_pct'] > 0.3 and c2['body_pct'] > 0.3 and c3['body_pct'] > 0.3 and
                c2['open'] < c1['open'] and c2['open'] > c1['close'] and
                c3['open'] < c2['open'] and c3['open'] > c2['close'] and
                c2['close'] < c1['close'] and c3['close'] < c2['close']):
                
                confidence = self._calculate_three_candle_confidence(c1, c2, c3, 'crows')
                patterns.append(Pattern(
                    type=PatternType.THREE_BLACK_CROWS,
                    confidence=confidence,
                    timeframe=timeframe,
                    timestamp=c3['timestamp'],
                    index=i
                ))
        
        return patterns
    
    # Confidence calculation methods
    
    def _calculate_doji_confidence(self, row: pd.Series, variant: str) -> float:
        """Calculate confidence score for doji patterns."""
        base_confidence = 0.7
        
        # Smaller body = higher confidence
        body_factor = max(0, 1 - row['body_pct'] / self.config.doji_threshold)
        
        if variant == 'dragonfly':
            # Longer lower shadow = higher confidence
            shadow_factor = min(1.0, row['lower_shadow_pct'] / 0.7)
            return min(0.95, base_confidence + body_factor * 0.15 + shadow_factor * 0.1)
        elif variant == 'gravestone':
            # Longer upper shadow = higher confidence
            shadow_factor = min(1.0, row['upper_shadow_pct'] / 0.7)
            return min(0.95, base_confidence + body_factor * 0.15 + shadow_factor * 0.1)
        else:  # standard
            return min(0.9, base_confidence + body_factor * 0.2)
    
    def _calculate_hammer_confidence(self, row: pd.Series) -> float:
        """Calculate confidence score for hammer patterns."""
        base_confidence = 0.75
        
        # Longer shadow = higher confidence
        shadow_factor = min(1.0, max(row['lower_shadow_pct'], row['upper_shadow_pct']) / 0.7)
        
        # Smaller body = higher confidence
        body_factor = max(0, 1 - row['body_pct'] / 0.3)
        
        return min(0.95, base_confidence + shadow_factor * 0.1 + body_factor * 0.1)
    
    def _calculate_engulfing_confidence(self, prev: pd.Series, curr: pd.Series, 
                                        direction: str) -> float:
        """Calculate confidence score for engulfing patterns."""
        base_confidence = 0.8
        
        # Calculate how much the current candle engulfs the previous
        prev_body = prev['body']
        engulfment = curr['body'] / prev_body if prev_body > 0 else 1.0
        engulfment_factor = min(1.0, (engulfment - 1) / 2)  # Normalize
        
        # Larger range = stronger signal
        range_factor = min(1.0, curr['range'] / (prev['range'] * 1.5)) if prev['range'] > 0 else 0.5
        
        return min(0.95, base_confidence + engulfment_factor * 0.1 + range_factor * 0.05)
    
    def _calculate_star_confidence(self, first: pd.Series, middle: pd.Series, 
                                   last: pd.Series, direction: str) -> float:
        """Calculate confidence score for star patterns."""
        base_confidence = 0.75
        
        # Smaller middle body = clearer star
        star_factor = max(0, 1 - middle['body_pct'] / 0.3)
        
        # Stronger first and last candles = stronger reversal
        first_strength = first['body_pct']
        last_strength = last['body_pct']
        strength_factor = (first_strength + last_strength) / 2
        
        return min(0.95, base_confidence + star_factor * 0.1 + strength_factor * 0.1)
    
    def _calculate_three_candle_confidence(self, c1: pd.Series, c2: pd.Series, 
                                           c3: pd.Series, pattern: str) -> float:
        """Calculate confidence score for three candle patterns."""
        base_confidence = 0.8
        
        # Consistent body sizes = higher confidence
        bodies = [c1['body_pct'], c2['body_pct'], c3['body_pct']]
        avg_body = sum(bodies) / 3
        consistency = 1 - (max(bodies) - min(bodies))  # Higher when similar
        
        # Progressive closes = higher confidence
        if pattern == 'soldiers':
            progression = (c3['close'] - c1['open']) / (c1['range'] + c2['range'] + c3['range'])
        else:  # crows
            progression = (c1['open'] - c3['close']) / (c1['range'] + c2['range'] + c3['range'])
        
        progression_factor = min(1.0, max(0, progression))
        
        return min(0.95, base_confidence + consistency * 0.075 + progression_factor * 0.075)
    
    def get_recent_patterns(self, df: pd.DataFrame, timeframe: Timeframe, 
                           n: int = 5) -> List[Pattern]:
        """
        Get patterns from the most recent n candles.
        
        Args:
            df: OHLCV DataFrame
            timeframe: Timeframe of data
            n: Number of recent candles to check
        
        Returns:
            List of patterns found in recent candles
        """
        all_patterns = self.detect_all_patterns(df, timeframe)
        
        if not all_patterns:
            return []
        
        # Get the index of the most recent candle
        latest_idx = len(df) - 1
        
        # Filter patterns from recent candles
        recent = [p for p in all_patterns if p.index >= latest_idx - n + 1]
        
        return recent