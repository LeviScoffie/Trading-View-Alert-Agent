"""
Multi-Timeframe Analysis Module.
Analyzes multiple timeframes together for confluence and divergence detection.
"""

import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime

from models import (
    Timeframe, TimeframeContext, MultiTimeframeContext, 
    TrendDirection, Config
)
from pattern_detector import PatternDetector
from ma_analyzer import MAAnalyzer


class MultiTimeframeAnalyzer:
    """
    Analyzes multiple timeframes for trend alignment and divergence.
    
    Timeframe weights (higher = more important):
    - Weekly: 0.4
    - Daily: 0.3
    - 4H: 0.2
    - 1H: 0.1
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.pattern_detector = PatternDetector(config)
        self.ma_analyzer = MAAnalyzer(config)
    
    def analyze(
        self,
        data: Dict[Timeframe, pd.DataFrame],
        primary_timeframe: Timeframe = Timeframe.DAILY
    ) -> MultiTimeframeContext:
        """
        Analyze multiple timeframes for confluence.
        
        Args:
            data: Dictionary mapping timeframe to OHLCV DataFrame
            primary_timeframe: The main timeframe being analyzed
        
        Returns:
            MultiTimeframeContext with alignment analysis
        """
        contexts = {}
        
        # Analyze each timeframe
        for timeframe, df in data.items():
            if df.empty:
                continue
            
            context = self._analyze_single_timeframe(df, timeframe)
            contexts[timeframe] = context
        
        # Calculate overall alignment
        alignment_score = self._calculate_alignment(contexts, primary_timeframe)
        
        # Detect divergences
        divergence = self._detect_divergence(contexts)
        
        # Build result
        return MultiTimeframeContext(
            weekly=contexts.get(Timeframe.WEEKLY),
            daily=contexts.get(Timeframe.DAILY),
            four_hour=contexts.get(Timeframe.FOUR_HOUR),
            one_hour=contexts.get(Timeframe.ONE_HOUR),
            overall_alignment=round(alignment_score, 2),
            divergence_detected=divergence
        )
    
    def _analyze_single_timeframe(self, df: pd.DataFrame, 
                                   timeframe: Timeframe) -> TimeframeContext:
        """Analyze a single timeframe."""
        # Detect patterns
        patterns = self.pattern_detector.detect_all_patterns(df, timeframe)
        
        # Analyze MA20
        ma20 = self.ma_analyzer.analyze(df)
        
        # Determine trend
        trend = self._determine_timeframe_trend(df, ma20, patterns)
        
        return TimeframeContext(
            trend=trend,
            alignment=False,  # Will be set later
            ma20=ma20,
            patterns=patterns[-5:] if patterns else []  # Last 5 patterns
        )
    
    def _determine_timeframe_trend(
        self,
        df: pd.DataFrame,
        ma20: Optional,
        patterns: List
    ) -> TrendDirection:
        """Determine the trend for a single timeframe."""
        scores = {'bullish': 0, 'bearish': 0, 'neutral': 0}
        
        # MA20 trend
        if ma20:
            if ma20.trend == TrendDirection.BULLISH:
                scores['bullish'] += 2
            elif ma20.trend == TrendDirection.BEARISH:
                scores['bearish'] += 2
            
            # Slope adds weight
            if ma20.slope.value == 'rising':
                scores['bullish'] += 1
            elif ma20.slope.value == 'falling':
                scores['bearish'] += 1
        
        # Pattern signals
        for p in patterns:
            if p.type in [
                'bullish_engulfing', 'hammer', 'morning_star',
                'three_white_soldiers', 'dragonfly_doji'
            ]:
                scores['bullish'] += p.confidence
            elif p.type in [
                'bearish_engulfing', 'evening_star',
                'three_black_crows', 'gravestone_doji'
            ]:
                scores['bearish'] += p.confidence
            elif p.type == 'doji':
                scores['neutral'] += p.confidence * 0.5
        
        # Recent price action
        if len(df) >= 5:
            recent = df.tail(5)
            first_close = recent['close'].iloc[0]
            last_close = recent['close'].iloc[-1]
            
            change = (last_close - first_close) / first_close
            
            if change > 0.02:  # 2% up
                scores['bullish'] += 1.5
            elif change < -0.02:  # 2% down
                scores['bearish'] += 1.5
        
        # Determine winner
        if scores['bullish'] > scores['bearish'] and scores['bullish'] > scores['neutral']:
            return TrendDirection.BULLISH
        elif scores['bearish'] > scores['bullish'] and scores['bearish'] > scores['neutral']:
            return TrendDirection.BEARISH
        
        return TrendDirection.NEUTRAL
    
    def _calculate_alignment(
        self,
        contexts: Dict[Timeframe, TimeframeContext],
        primary_timeframe: Timeframe
    ) -> float:
        """
        Calculate overall alignment score across timeframes.
        
        Returns score between 0 and 1 where 1 = perfect alignment.
        """
        if not contexts:
            return 0.0
        
        # Get primary trend
        primary = contexts.get(primary_timeframe)
        if not primary:
            return 0.5
        
        primary_trend = primary.trend
        
        # Calculate weighted alignment
        total_weight = 0
        aligned_weight = 0
        
        weights = self.config.confidence_weights
        
        for timeframe, context in contexts.items():
            weight = weights.get(timeframe.value, 0.1)
            total_weight += weight
            
            # Mark alignment
            context.alignment = (context.trend == primary_trend)
            
            if context.alignment:
                aligned_weight += weight
        
        if total_weight == 0:
            return 0.5
        
        return aligned_weight / total_weight
    
    def _detect_divergence(self, contexts: Dict[Timeframe, TimeframeContext]) -> bool:
        """
        Detect if there's significant divergence between timeframes.
        
        Returns True if divergences detected.
        """
        if len(contexts) < 2:
            return False
        
        trends = [c.trend for c in contexts.values()]
        
        # Check for mixed signals
        has_bullish = TrendDirection.BULLISH in trends
        has_bearish = TrendDirection.BEARISH in trends
        
        # Divergence exists if we have both bullish and bearish timeframes
        if has_bullish and has_bearish:
            return True
        
        # Check for strong trend in higher TF vs weak/neutral in lower TF
        weekly = contexts.get(Timeframe.WEEKLY)
        daily = contexts.get(Timeframe.DAILY)
        
        if weekly and daily:
            # If weekly is strong but daily contradicts
            if weekly.trend == TrendDirection.BULLISH and daily.trend == TrendDirection.BEARISH:
                return True
            if weekly.trend == TrendDirection.BEARISH and daily.trend == TrendDirection.BULLISH:
                return True
        
        return False
    
    def get_alignment_summary(self, mtf_context: MultiTimeframeContext) -> str:
        """Generate human-readable alignment summary."""
        parts = []
        
        if mtf_context.weekly:
            parts.append(f"Weekly: {mtf_context.weekly.trend.value}")
        if mtf_context.daily:
            parts.append(f"Daily: {mtf_context.daily.trend.value}")
        if mtf_context.four_hour:
            parts.append(f"4H: {mtf_context.four_hour.trend.value}")
        if mtf_context.one_hour:
            parts.append(f"1H: {mtf_context.one_hour.trend.value}")
        
        alignment_pct = int(mtf_context.overall_alignment * 100)
        divergence = "DIVERGENCE DETECTED" if mtf_context.divergence_detected else "aligned"
        
        return f"Alignment: {alignment_pct}% ({divergence}) | " + " | ".join(parts)
    
    def get_primary_trend(self, mtf_context: MultiTimeframeContext) -> TrendDirection:
        """Get the dominant trend across all timeframes."""
        weights = {
            mtf_context.weekly: 0.4,
            mtf_context.daily: 0.3,
            mtf_context.four_hour: 0.2,
            mtf_context.one_hour: 0.1
        }
        
        scores = {'bullish': 0, 'bearish': 0, 'neutral': 0}
        
        for context, weight in weights.items():
            if context:
                scores[context.trend.value] += weight
        
        max_trend = max(scores, key=scores.get)
        
        if max_trend == 'bullish':
            return TrendDirection.BULLISH
        elif max_trend == 'bearish':
            return TrendDirection.BEARISH
        
        return TrendDirection.NEUTRAL