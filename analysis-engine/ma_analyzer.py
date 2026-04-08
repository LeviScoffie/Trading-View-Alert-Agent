"""
Moving Average Analyzer Module.
Calculates 20-period MA and analyzes trend/slope.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple

from models import MA20Analysis, TrendDirection, SlopeDirection, Config


class MAAnalyzer:
    """
    Analyzes price relative to 20-period moving average.
    
    Provides:
    - Distance from MA (as percentage)
    - Trend direction (above/below MA)
    - Slope analysis (rising, falling, flat)
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.period = config.ma_period if config else 20
    
    def calculate_ma20(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate 20-period moving average.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            DataFrame with added 'ma20' column
        """
        df = df.copy()
        df['ma20'] = df['close'].rolling(window=self.period, min_periods=self.period).mean()
        return df
    
    def analyze(self, df: pd.DataFrame) -> Optional[MA20Analysis]:
        """
        Perform complete MA20 analysis on the dataset.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            MA20Analysis object or None if insufficient data
        """
        if len(df) < self.period:
            return None
        
        df = self.calculate_ma20(df)
        
        # Get the most recent valid row
        last_valid = df.dropna(subset=['ma20']).iloc[-1]
        
        price = last_valid['close']
        ma20 = last_valid['ma20']
        
        # Calculate distance as percentage
        distance_pct = ((price - ma20) / ma20) * 100
        
        # Determine trend direction
        trend = TrendDirection.BULLISH if price > ma20 else TrendDirection.BEARISH
        
        # Calculate slope
        slope, slope_direction = self._calculate_slope(df)
        
        return MA20Analysis(
            price=price,
            ma20=ma20,
            distance_pct=round(distance_pct, 2),
            trend=trend,
            slope=slope_direction,
            slope_value=round(slope, 6)
        )
    
    def _calculate_slope(self, df: pd.DataFrame, lookback: int = 5) -> Tuple[float, SlopeDirection]:
        """
        Calculate the slope of the MA20 line.
        
        Args:
            df: DataFrame with 'ma20' column
            lookback: Number of periods to calculate slope over
        
        Returns:
            Tuple of (slope_value, slope_direction)
        """
        df = df.dropna(subset=['ma20'])
        
        if len(df) < lookback:
            return 0.0, SlopeDirection.FLAT
        
        # Get recent MA values
        recent = df['ma20'].iloc[-lookback:].values
        
        # Calculate slope using linear regression
        x = np.arange(len(recent))
        slope = np.polyfit(x, recent, 1)[0]
        
        # Normalize slope as percentage of MA value
        avg_ma = np.mean(recent)
        normalized_slope = (slope / avg_ma) * 100 if avg_ma != 0 else 0
        
        # Determine direction
        threshold = self.config.slope_threshold
        if normalized_slope > threshold:
            direction = SlopeDirection.RISING
        elif normalized_slope < -threshold:
            direction = SlopeDirection.FALLING
        else:
            direction = SlopeDirection.FLAT
        
        return normalized_slope, direction
    
    def get_ma_cross_status(self, df: pd.DataFrame) -> Optional[str]:
        """
        Detect if price recently crossed above or below MA20.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            'crossed_above', 'crossed_below', or None
        """
        if len(df) < self.period + 2:
            return None
        
        df = self.calculate_ma20(df)
        df = df.dropna(subset=['ma20'])
        
        if len(df) < 3:
            return None
        
        # Check last 3 candles
        recent = df.iloc[-3:]
        
        prev = recent.iloc[-2]
        curr = recent.iloc[-1]
        
        # Check for cross above
        if prev['close'] < prev['ma20'] and curr['close'] > curr['ma20']:
            return 'crossed_above'
        
        # Check for cross below
        if prev['close'] > prev['ma20'] and curr['close'] < curr['ma20']:
            return 'crossed_below'
        
        return None
    
    def get_distance_history(self, df: pd.DataFrame, periods: int = 20) -> pd.DataFrame:
        """
        Get historical distance from MA20.
        
        Args:
            df: DataFrame with OHLCV data
            periods: Number of periods to return
        
        Returns:
            DataFrame with 'distance_pct' column
        """
        df = self.calculate_ma20(df)
        df['distance_pct'] = ((df['close'] - df['ma20']) / df['ma20']) * 100
        return df[['timestamp', 'close', 'ma20', 'distance_pct']].dropna().tail(periods)
    
    def get_support_resistance_levels(self, df: pd.DataFrame, n_levels: int = 3) -> Tuple[list, list]:
        """
        Estimate support and resistance levels based on MA20 and price action.
        
        Args:
            df: DataFrame with OHLCV data
            n_levels: Number of levels to return
        
        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        df = self.calculate_ma20(df)
        
        recent = df.tail(50)  # Look at last 50 candles
        
        current_price = df['close'].iloc[-1]
        current_ma = df['ma20'].iloc[-1]
        
        # Find local minima/maxima
        supports = []
        resistances = []
        
        # Use recent lows as supports
        for i in range(1, len(recent) - 1):
            if (recent['low'].iloc[i] < recent['low'].iloc[i-1] and 
                recent['low'].iloc[i] < recent['low'].iloc[i+1]):
                supports.append(recent['low'].iloc[i])
        
        # Use recent highs as resistances
        for i in range(1, len(recent) - 1):
            if (recent['high'].iloc[i] > recent['high'].iloc[i-1] and 
                recent['high'].iloc[i] > recent['high'].iloc[i+1]):
                resistances.append(recent['high'].iloc[i])
        
        # Add MA20 as dynamic level
        if current_price > current_ma:
            supports.append(current_ma)
        else:
            resistances.append(current_ma)
        
        # Sort and get closest levels
        supports = sorted([s for s in supports if s < current_price], reverse=True)[:n_levels]
        resistances = sorted([r for r in resistances if r > current_price])[:n_levels]
        
        return supports, resistances
