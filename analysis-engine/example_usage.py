#!/usr/bin/env python3
"""
Example usage of the Analysis Engine.
Demonstrates full analysis flow with sample data.
"""

import sys
from datetime import datetime, timedelta
from models import Timeframe, Config, OHLCV
from analysis_engine import AnalysisEngine, analyze


def create_sample_data():
    """Create sample OHLCV data for testing."""
    base_price = 45000
    base_time = datetime(2026, 4, 1)
    
    # Create 30 days of sample data with some patterns
    data = []
    for i in range(30):
        timestamp = base_time + timedelta(days=i)
        
        # Simulate some price movement
        if i < 5:
            # Downtrend (for Rule 1: bearish pullback)
            open_price = base_price - i * 200
            close_price = open_price - 100
            high = open_price + 50
            low = close_price - 100
        elif i == 5:
            # Bullish engulfing day
            open_price = base_price - 1200
            close_price = base_price - 800
            high = close_price + 100
            low = open_price - 50
        else:
            # Uptrend
            open_price = base_price - 800 + (i - 5) * 150
            close_price = open_price + 200
            high = close_price + 100
            low = open_price - 50
        
        data.append(OHLCV(
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close_price,
            volume=1000000 + i * 10000
        ))
    
    return data


def main():
    """Run example analysis."""
    print("=" * 60)
    print("Analysis Engine - Example Usage")
    print("=" * 60)
    
    # Initialize engine
    config = Config(db_path=":memory:")  # In-memory database for demo
    engine = AnalysisEngine(config=config)
    
    # Create and store sample data
    print("\n1. Creating sample OHLCV data...")
    sample_data = create_sample_data()
    
    engine.store_ohlcv_data("BTCUSD", Timeframe.DAILY, [
        {
            "timestamp": d.timestamp.isoformat(),
            "open": d.open,
            "high": d.high,
            "low": d.low,
            "close": d.close,
            "volume": d.volume
        }
        for d in sample_data
    ])
    print(f"   Stored {len(sample_data)} daily candles")
    
    # Run analysis
    print("\n2. Running analysis on BTCUSD...")
    result = engine.analyze_symbol("BTCUSD", Timeframe.DAILY)
    
    # Display results
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    
    print(f"\n📊 Symbol: {result.symbol}")
    print(f"⏰ Timestamp: {result.timestamp}")
    
    # Patterns detected
    print(f"\n🔍 Patterns Detected: {len(result.patterns)}")
    if result.patterns:
        for p in result.patterns[-5:]:  # Last 5 patterns
            print(f"   • {p.type.value.replace('_', ' ').title()} "
                  f"(confidence: {p.confidence:.2f}, timeframe: {p.timeframe.value})")
    else:
        print("   No patterns detected in recent candles")
    
    # MA20 Analysis
    if result.ma20:
        print(f"\n📈 MA20 Analysis:")
        print(f"   Current Price: ${result.ma20.price:,.2f}")
        print(f"   MA20 Value: ${result.ma20.ma20:,.2f}")
        print(f"   Distance: {result.ma20.distance_pct:+.2f}%")
        print(f"   Trend: {result.ma20.trend.value}")
        print(f"   Slope: {result.ma20.slope.value}")
    
    # Multi-timeframe context
    if result.multi_timeframe:
        print(f"\n🌐 Multi-Timeframe Analysis:")
        print(f"   Overall Alignment: {result.multi_timeframe.overall_alignment:.0%}")
        print(f"   Divergence: {'Yes ⚠️' if result.multi_timeframe.divergence_detected else 'No ✓'}")
        
        if result.multi_timeframe.weekly:
            print(f"   Weekly: {result.multi_timeframe.weekly.trend.value}")
        if result.multi_timeframe.daily:
            print(f"   Daily: {result.multi_timeframe.daily.trend.value}")
        if result.multi_timeframe.four_hour:
            print(f"   4H: {result.multi_timeframe.four_hour.trend.value}")
    
    # Context analysis
    if result.context:
        print(f"\n🧠 Context Intelligence:")
        print(f"   Sentiment: {result.context.sentiment.value.upper()}")
        print(f"   Confidence: {result.context.confidence:.0%}")
        print(f"   Recommendation: {result.context.recommendation.value.replace('_', ' ').upper()}")
        
        if result.context.triggered_rules:
            print(f"\n   Triggered Rules:")
            for rule in result.context.triggered_rules:
                print(f"   ✓ {rule}")
        
        print(f"\n   Reasoning:")
        print(f"   {result.context.reasoning}")
        
        if result.context.key_levels:
            print(f"\n   Key Levels:")
            print(f"   Support: ${', $'.join(f'{l:,.0f}' for l in result.context.key_levels[:3])}")
            print(f"   Resistance: ${', $'.join(f'{l:,.0f}' for l in result.context.key_levels[3:])}")
    
    # JSON output
    print("\n" + "=" * 60)
    print("JSON OUTPUT")
    print("=" * 60)
    print(result.model_dump_json(indent=2))
    
    # Cleanup
    engine.close()
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
