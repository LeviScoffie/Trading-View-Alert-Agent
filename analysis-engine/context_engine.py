"""
Context Intelligence Engine.
Analyzes patterns and market conditions to generate confidence scores and recommendations.
"""

import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from models import (
    Pattern, PatternType, MA20Analysis, TrendDirection,
    ContextAnalysis, ContextRecommendation, Timeframe
)


class ContextEngine:
    """
    Context Intelligence Engine for trading signal analysis.
    
    Implements confidence scoring rules:
    - Rule 1: Past 2-3 days bearish + weekly engulfing = buying opportunity
    - Rule 2: Price > 20MA + bullish engulfing = high confidence
    - Rule 3: Price < 20MA + bearish engulfing = high confidence
    - Rule 4: Multiple timeframe alignment = higher confidence
    - Rule 5: Doji at support/resistance = potential reversal
    """
    
    def __init__(self):
        self.triggered_rules: List[str] = []
    
    def analyze(
        self,
        symbol: str,
        patterns: List[Pattern],
        ma20: Optional[MA20Analysis],
        df: pd.DataFrame,
        multi_timeframe_context: Optional[Dict] = None
    ) -> ContextAnalysis:
        """
        Perform context analysis on the current market conditions.
        
        Args:
            symbol: Trading symbol
            patterns: List of detected patterns
            ma20: MA20 analysis results
            df: OHLCV DataFrame
            multi_timeframe_context: Optional multi-timeframe analysis
        
        Returns:
            ContextAnalysis with sentiment, confidence, and recommendation
        """
        self.triggered_rules = []
        
        # Analyze recent price action
        recent_trend = self._analyze_recent_trend(df)
        
        # Check each context rule
        confidence_scores = []
        sentiments = []
        reasonings = []
        
        # Rule 1: Past 2-3 days bearish + weekly bullish engulfing
        rule1_score, rule1_reason = self._check_rule1(patterns, recent_trend, multi_timeframe_context)
        if rule1_score > 0:
            confidence_scores.append(rule1_score)
            sentiments.append(TrendDirection.BULLISH)
            reasonings.append(rule1_reason)
            self.triggered_rules.append("Rule 1: Bearish pullback + weekly engulfing")
        
        # Rule 2: Price > 20MA + bullish engulfing
        rule2_score, rule2_reason = self._check_rule2(patterns, ma20)
        if rule2_score > 0:
            confidence_scores.append(rule2_score)
            sentiments.append(TrendDirection.BULLISH)
            reasonings.append(rule2_reason)
            self.triggered_rules.append("Rule 2: Above MA20 + bullish engulfing")
        
        # Rule 3: Price < 20MA + bearish engulfing
        rule3_score, rule3_reason = self._check_rule3(patterns, ma20)
        if rule3_score > 0:
            confidence_scores.append(rule3_score)
            sentiments.append(TrendDirection.BEARISH)
            reasonings.append(rule3_reason)
            self.triggered_rules.append("Rule 3: Below MA20 + bearish engulfing")
        
        # Rule 4: Multiple timeframe alignment
        rule4_score, rule4_reason = self._check_rule4(multi_timeframe_context)
        if rule4_score > 0:
            confidence_scores.append(rule4_score)
            # Sentiment from multi-timeframe
            if multi_timeframe_context:
                weekly = multi_timeframe_context.get('weekly') or {}
                if weekly.get('trend') == TrendDirection.BULLISH:
                    sentiments.append(TrendDirection.BULLISH)
                elif weekly.get('trend') == TrendDirection.BEARISH:
                    sentiments.append(TrendDirection.BEARISH)
            reasonings.append(rule4_reason)
            self.triggered_rules.append("Rule 4: Multi-timeframe alignment")
        
        # Rule 5: Doji at support/resistance
        rule5_score, rule5_reason = self._check_rule5(patterns, df, ma20)
        if rule5_score > 0:
            confidence_scores.append(rule5_score)
            sentiments.append(TrendDirection.NEUTRAL)
            reasonings.append(rule5_reason)
            self.triggered_rules.append("Rule 5: Doji at key level")
        
        # Calculate final sentiment and confidence
        if not confidence_scores:
            # No rules triggered - neutral with low confidence
            return ContextAnalysis(
                sentiment=TrendDirection.NEUTRAL,
                confidence=0.3,
                reasoning="No strong context signals detected. Market conditions unclear.",
                key_levels=self._get_key_levels(df, ma20),
                recommendation=ContextRecommendation.WAIT,
                triggered_rules=[]
            )
        
        # Weight confidence by rule importance
        final_confidence = self._calculate_weighted_confidence(confidence_scores)
        
        # Determine dominant sentiment
        final_sentiment = self._determine_sentiment(sentiments, patterns)
        
        # Build reasoning string
        final_reasoning = self._build_reasoning(reasonings, patterns, recent_trend)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            final_sentiment, final_confidence, patterns, ma20
        )
        
        return ContextAnalysis(
            sentiment=final_sentiment,
            confidence=round(final_confidence, 2),
            reasoning=final_reasoning,
            key_levels=self._get_key_levels(df, ma20),
            recommendation=recommendation,
            triggered_rules=self.triggered_rules
        )
    
    def _analyze_recent_trend(self, df: pd.DataFrame, lookback: int = 3) -> str:
        """Analyze the trend over recent candles."""
        if len(df) < lookback:
            return "neutral"
        
        recent = df.tail(lookback)
        closes = recent['close'].values
        
        # Count up/down days
        up_days = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        down_days = (len(closes) - 1) - up_days
        
        if up_days > down_days:
            return "bullish"
        elif down_days > up_days:
            return "bearish"
        return "neutral"
    
    def _check_rule1(
        self, 
        patterns: List[Pattern], 
        recent_trend: str,
        multi_timeframe_context: Optional[Dict]
    ) -> Tuple[float, str]:
        """
        Rule 1: Past 2-3 days bearish + weekly bullish engulfing = buying opportunity.
        """
        # Check for recent bearish trend
        if recent_trend != "bearish":
            return 0, ""
        
        # Check for weekly bullish engulfing
        has_weekly_bullish = any(
            p.type == PatternType.BULLISH_ENGULFING and p.timeframe == Timeframe.WEEKLY
            for p in patterns
        )
        
        if has_weekly_bullish:
            return 0.85, f"Recent {recent_trend} pullback with weekly bullish engulfing suggests buying opportunity"
        
        return 0, ""
    
    def _check_rule2(self, patterns: List[Pattern], ma20: Optional[MA20Analysis]) -> Tuple[float, str]:
        """
        Rule 2: Price > 20MA + bullish engulfing = high confidence bullish.
        """
        if ma20 is None:
            return 0, ""
        
        # Check if price is above MA20
        if ma20.trend != TrendDirection.BULLISH:
            return 0, ""
        
        # Check for bullish engulfing
        has_bullish_engulfing = any(
            p.type == PatternType.BULLISH_ENGULFING
            for p in patterns
        )
        
        if has_bullish_engulfing:
            distance = abs(ma20.distance_pct)
            confidence = min(0.9, 0.75 + (distance / 100))
            return confidence, f"Price {ma20.distance_pct:.2f}% above MA20 with bullish engulfing - high confidence bullish signal"
        
        return 0, ""
    
    def _check_rule3(self, patterns: List[Pattern], ma20: Optional[MA20Analysis]) -> Tuple[float, str]:
        """
        Rule 3: Price < 20MA + bearish engulfing = high confidence bearish.
        """
        if ma20 is None:
            return 0, ""
        
        # Check if price is below MA20
        if ma20.trend != TrendDirection.BEARISH:
            return 0, ""
        
        # Check for bearish engulfing
        has_bearish_engulfing = any(
            p.type == PatternType.BEARISH_ENGULFING
            for p in patterns
        )
        
        if has_bearish_engulfing:
            distance = abs(ma20.distance_pct)
            confidence = min(0.9, 0.75 + (distance / 100))
            return confidence, f"Price {ma20.distance_pct:.2f}% below MA20 with bearish engulfing - high confidence bearish signal"
        
        return 0, ""
    
    def _check_rule4(self, multi_timeframe_context: Optional[Dict]) -> Tuple[float, str]:
        """
        Rule 4: Multiple timeframe alignment = higher confidence.
        """
        if not multi_timeframe_context:
            return 0, ""
        
        # Count aligned timeframes
        aligned_count = 0
        total_count = 0
        
        for tf, context in multi_timeframe_context.items():
            if tf == 'overall_alignment':
                continue
            if isinstance(context, dict) and 'alignment' in context:
                total_count += 1
                if context['alignment']:
                    aligned_count += 1
        
        if total_count == 0:
            return 0, ""
        
        alignment_ratio = aligned_count / total_count
        
        if alignment_ratio >= 0.75:  # 75%+ aligned
            return 0.8 + (alignment_ratio - 0.75) * 0.4, f"{aligned_count}/{total_count} timeframes aligned - strong confluence"
        elif alignment_ratio >= 0.5:  # 50%+ aligned
            return 0.6 + (alignment_ratio - 0.5) * 0.4, f"{aligned_count}/{total_count} timeframes aligned - moderate confluence"
        
        return 0, ""
    
    def _check_rule5(self, patterns: List[Pattern], df: pd.DataFrame, 
                     ma20: Optional[MA20Analysis]) -> Tuple[float, str]:
        """
        Rule 5: Doji at support/resistance = potential reversal.
        """
        # Check for doji patterns
        doji_patterns = [p for p in patterns if p.type in [
            PatternType.DOJI, PatternType.DRAGONFLY_DOJI, PatternType.GRAVESTONE_DOJI
        ]]
        
        if not doji_patterns:
            return 0, ""
        
        if len(df) < 2:
            return 0, ""
        
        current_price = df['close'].iloc[-1]
        
        # Check if price is near recent support/resistance
        recent = df.tail(20)
        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        
        # Calculate proximity to key levels
        near_resistance = (recent_high - current_price) / current_price < 0.02  # Within 2%
        near_support = (current_price - recent_low) / current_price < 0.02
        
        # Check proximity to MA20
        near_ma20 = False
        if ma20:
            ma_distance = abs((current_price - ma20.ma20) / ma20.ma20)
            near_ma20 = ma_distance < 0.01  # Within 1%
        
        if near_resistance:
            return 0.75, "Doji pattern near resistance level - potential bearish reversal"
        elif near_support:
            return 0.75, "Doji pattern near support level - potential bullish reversal"
        elif near_ma20:
            return 0.7, "Doji pattern at MA20 level - potential reversal point"
        
        return 0, ""
    
    def _calculate_weighted_confidence(self, scores: List[float]) -> float:
        """Calculate weighted average confidence score."""
        if not scores:
            return 0.5
        
        # Weight higher scores more heavily
        weights = [1 + (s - 0.5) for s in scores]  # Higher scores get higher weights
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        total_weight = sum(weights)
        
        return min(0.95, weighted_sum / total_weight)
    
    def _determine_sentiment(self, sentiments: List[TrendDirection], 
                            patterns: List[Pattern]) -> TrendDirection:
        """Determine the dominant sentiment."""
        if not sentiments:
            # Fall back to pattern analysis
            bullish = sum(1 for p in patterns if p.type in [
                PatternType.BULLISH_ENGULFING, PatternType.HAMMER,
                PatternType.MORNING_STAR, PatternType.THREE_WHITE_SOLDIERS,
                PatternType.DRAGONFLY_DOJI
            ])
            bearish = sum(1 for p in patterns if p.type in [
                PatternType.BEARISH_ENGULFING, PatternType.EVENING_STAR,
                PatternType.THREE_BLACK_CROWS, PatternType.GRAVESTONE_DOJI
            ])
            
            if bullish > bearish:
                return TrendDirection.BULLISH
            elif bearish > bullish:
                return TrendDirection.BEARISH
            return TrendDirection.NEUTRAL
        
        # Count sentiment occurrences
        bullish_count = sentiments.count(TrendDirection.BULLISH)
        bearish_count = sentiments.count(TrendDirection.BEARISH)
        neutral_count = sentiments.count(TrendDirection.NEUTRAL)
        
        if bullish_count > bearish_count and bullish_count > neutral_count:
            return TrendDirection.BULLISH
        elif bearish_count > bullish_count and bearish_count > neutral_count:
            return TrendDirection.BEARISH
        
        return TrendDirection.NEUTRAL
    
    def _build_reasoning(self, reasonings: List[str], patterns: List[Pattern],
                        recent_trend: str) -> str:
        """Build comprehensive reasoning string."""
        parts = []
        
        # Add triggered rule reasonings
        for r in reasonings:
            if r:
                parts.append(r)
        
        # Add pattern summary
        if patterns:
            pattern_names = [p.type.value.replace('_', ' ').title() for p in patterns[-3:]]
            parts.append(f"Recent patterns: {', '.join(pattern_names)}")
        
        # Add trend context
        if recent_trend != "neutral":
            parts.append(f"Recent {recent_trend} price action")
        
        return "; ".join(parts) if parts else "Market conditions under analysis"
    
    def _get_key_levels(self, df: pd.DataFrame, ma20: Optional[MA20Analysis]) -> List[float]:
        """Extract key support/resistance levels."""
        if len(df) < 20:
            return []
        
        levels = []
        
        # Add MA20 as dynamic level
        if ma20:
            levels.append(round(ma20.ma20, 2))
        
        # Add recent swing highs/lows
        recent = df.tail(20)
        
        # Find local extrema
        for i in range(1, len(recent) - 1):
            # Local high
            if (recent['high'].iloc[i] > recent['high'].iloc[i-1] and 
                recent['high'].iloc[i] > recent['high'].iloc[i+1]):
                levels.append(round(recent['high'].iloc[i], 2))
            
            # Local low
            if (recent['low'].iloc[i] < recent['low'].iloc[i-1] and 
                recent['low'].iloc[i] < recent['low'].iloc[i+1]):
                levels.append(round(recent['low'].iloc[i], 2))
        
        # Remove duplicates and sort
        levels = sorted(list(set(levels)))
        
        # Return closest levels to current price
        if levels and len(df) > 0:
            current = df['close'].iloc[-1]
            # Get levels within 10% of current price
            relevant = [l for l in levels if abs(l - current) / current < 0.1]
            return relevant[:5] if relevant else [round(current * 0.95, 2), round(current * 1.05, 2)]
        
        return levels
    
    def _generate_recommendation(
        self,
        sentiment: TrendDirection,
        confidence: float,
        patterns: List[Pattern],
        ma20: Optional[MA20Analysis]
    ) -> ContextRecommendation:
        """Generate trading recommendation based on analysis."""
        
        # High confidence bullish
        if sentiment == TrendDirection.BULLISH and confidence >= 0.8:
            return ContextRecommendation.STRONG_LONG
        
        # Moderate confidence bullish
        if sentiment == TrendDirection.BULLISH and confidence >= 0.6:
            return ContextRecommendation.CONSIDER_LONG
        
        # High confidence bearish
        if sentiment == TrendDirection.BEARISH and confidence >= 0.8:
            return ContextRecommendation.STRONG_SHORT
        
        # Moderate confidence bearish
        if sentiment == TrendDirection.BEARISH and confidence >= 0.6:
            return ContextRecommendation.CONSIDER_SHORT
        
        # Low confidence or neutral
        if confidence < 0.5:
            return ContextRecommendation.WAIT
        
        return ContextRecommendation.NEUTRAL
