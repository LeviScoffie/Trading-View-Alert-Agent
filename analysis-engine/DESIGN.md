# Design Document: Analysis Engine

## Overview

This document describes the architecture, design decisions, and implementation details of the Analysis Engine for the TradingView Alert Agent.

## Problem Statement

TradingView alerts provide raw pattern signals ("Bullish Engulfing on BTCUSD") without context. This leads to:
- False positives from isolated patterns
- Missed confluence signals across timeframes
- No confidence scoring for signal quality
- No integration with trend analysis (moving averages)

## Solution

A modular analysis engine that adds context intelligence to raw alerts through:
1. Multi-pattern detection
2. Moving average trend analysis
3. Context rule engine with confidence scoring
4. Multi-timeframe confluence detection

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        TradingView Alert                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AnalysisEngine                              │
│                   (Main Orchestrator)                            │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  1. Fetch OHLCV data from SQLite                       │     │
│  │  2. Run pattern detection                              │     │
│  │  3. Calculate MA20 analysis                            │     │
│  │  4. Perform multi-timeframe analysis                   │     │
│  │  5. Apply context rules                                │     │
│  │  6. Generate final recommendation                      │     │
│  └────────────────────────────────────────────────────────┘     │
└──────────────┬──────────────────────────────────────────────────┘
               │
    ┌──────────┼────────────┬───────────────┬─────────────┐
    │          │            │               │             │
    ▼          ▼            ▼               ▼             ▼
┌─────────┐ ┌────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐
│ Pattern │ │  MA20  │ │ Context  │ │   Multi   │ │  SQLite  │
│ Detector│ │Analyzer│ │  Engine  │ │ Timeframe │ │ Database │
└─────────┘ └────────┘ └──────────┘ └───────────┘ └──────────┘
```

### Data Flow

```
Alert Received
     │
     ▼
┌─────────────────┐
│ Fetch OHLCV     │─────────────────────┐
│ from Database   │                     │
└────────┬────────┘                     │
         │                              │
         ▼                              │
┌─────────────────┐                     │
│ Pattern         │─────┐               │
│ Detection       │     │               │
└────────┬────────┘     │               │
         │              │               │
         ▼              │               │
┌─────────────────┐     │               │
│ MA20 Analysis   │─────┤               │
└────────┬────────┘     │               │
         │              │               │
         ▼              │               │
┌─────────────────┐     │               │
│ Multi-Timeframe │─────┤               │
│ Analysis        │     │               │
└────────┬────────┘     │               │
         │              │               │
         ▼              │               │
┌─────────────────┐     │               │
│ Context Engine  │◄────┘               │
│ (Applies Rules) │                     │
└────────┬────────┘                     │
         │                              │
         ▼                              │
┌─────────────────┐                     │
│ Generate JSON   │                     │
│ Output          │                     │
└─────────────────┘                     │
                                        │
┌───────────────────────────────────────┘
│
▼
Notification Sent
```

## Design Decisions

### 1. Modular Architecture

**Decision:** Separate concerns into distinct modules (pattern_detector, ma_analyzer, context_engine, multi_timeframe).

**Rationale:**
- Each module has a single responsibility
- Easier to test in isolation
- Can be replaced/updated independently
- Clear interfaces between components

**Trade-offs:**
- More files to manage
- Some code duplication in data passing
- Requires careful interface design

### 2. SQLite for Data Storage

**Decision:** Use SQLite instead of PostgreSQL/InfluxDB.

**Rationale:**
- Zero configuration required
- Single file database
- Sufficient for OHLCV data at our scale
- Built into Python standard library
- Easy to backup/migrate

**Trade-offs:**
- Not suitable for high-frequency data (tick-level)
- Limited concurrent write support
- No built-in time-series optimizations

**Mitigation:**
- Use indexes on (symbol, timeframe, timestamp)
- Implement data pruning for old records
- Can migrate to TimescaleDB if needed later

### 3. Pydantic for Data Models

**Decision:** Use Pydantic v2 for all data structures.

**Rationale:**
- Automatic validation
- Type hints for IDE support
- Easy JSON serialization
- Clear data contracts between modules
- Built-in documentation via model schema

**Trade-offs:**
- Runtime validation overhead (minimal)
- Additional dependency

### 4. Confidence Scoring System

**Decision:** Implement weighted confidence scoring (0-1 scale) rather than binary signals.

**Rationale:**
- Real trading decisions exist on a spectrum
- Allows threshold tuning based on risk tolerance
- Multiple weak signals can combine into strong signal
- Easier to explain to users ("82% confidence")

**Implementation:**
```python
# Base confidence per rule
Rule 1: 0.85 (bearish pullback + weekly engulfing)
Rule 2: 0.75-0.90 (above MA20 + bullish, scales with distance)
Rule 3: 0.75-0.90 (below MA20 + bearish, scales with distance)
Rule 4: 0.60-0.80 (multi-timeframe alignment)
Rule 5: 0.70-0.75 (doji at key level)

# Final confidence = weighted average
# Higher scores get higher weights
```

### 5. Timeframe Weighting

**Decision:** Weight higher timeframes more heavily.

**Weights:**
- Weekly: 40%
- Daily: 30%
- 4H: 20%
- 1H: 10%

**Rationale:**
- Higher timeframes have more signal, less noise
- Weekly trend should dominate intraday noise
- Aligns with professional trading practices
- Reduces false signals from lower timeframe whipsaws

**Trade-offs:**
- May miss short-term opportunities
- Less responsive to rapid trend changes

### 6. Pattern Detection Algorithm

**Decision:** Rule-based pattern detection with configurable thresholds.

**Rationale:**
- Transparent and explainable
- No training data required
- Fast execution (O(n) for n candles)
- Easy to tune thresholds
- Deterministic results

**Alternative Considered:** ML-based pattern recognition

**Why Not ML:**
- Requires labeled training data
- Black box predictions
- Harder to debug
- Overkill for well-defined patterns
- Slower inference

### 7. Context Rules Engine

**Decision:** Hard-coded rules with clear documentation.

**Rationale:**
- Rules encode trading wisdom
- Easy to understand and audit
- Can be A/B tested
- Users can see which rules triggered

**Future Enhancement:** Configurable rules via YAML/JSON config file.

### 8. Output Format

**Decision:** JSON output with nested structure.

**Rationale:**
- Easy to parse in any language
- Works with webhooks/APIs
- Human-readable with indentation
- Compatible with notification systems

## Implementation Details

### Pattern Detection Logic

Each pattern type has specific detection criteria:

**Engulfing:**
```python
# Bullish: Previous red, current green, current body engulfs previous
if (prev.close < prev.open and  # Previous red
    curr.close > curr.open and  # Current green
    curr.open < prev.close and  # Opens below previous close
    curr.close > prev.open):    # Closes above previous open
    return BULLISH_ENGULFING
```

**Doji:**
```python
# Body less than 1% of total range
if body / range < 0.01:
    if lower_shadow > 0.6 * range:
        return DRAGONFLY_DOJI
    elif upper_shadow > 0.6 * range:
        return GRAVESTONE_DOJI
    else:
        return DOJI
```

**Three White Soldiers:**
```python
# Three consecutive green candles with progressive closes
if (c1.green and c2.green and c3.green and
    c2.open within c1.body and
    c3.open within c2.body and
    c3.close > c2.close > c1.close):
    return THREE_WHITE_SOLDIERS
```

### MA20 Calculation

```python
# Simple moving average of closing prices
ma20 = close.rolling(window=20).mean()

# Distance as percentage
distance_pct = (price - ma20) / ma20 * 100

# Slope via linear regression
slope = np.polyfit(x=range(5), y=ma20[-5:], deg=1)[0]
```

### Context Rule Implementation

```python
def check_rule1(patterns, recent_trend, mtf_context):
    """Past 2-3 days bearish + weekly bullish engulfing = buy"""
    if recent_trend != "bearish":
        return 0, ""
    
    has_weekly_bullish = any(
        p.type == BULLISH_ENGULFING and p.timeframe == WEEKLY
        for p in patterns
    )
    
    if has_weekly_bullish:
        return 0.85, "Bearish pullback + weekly engulfing = buy"
    return 0, ""
```

## Testing Strategy

### Unit Tests (`test_patterns.py`)

- Test each pattern type with synthetic data
- Verify confidence scores in valid range [0, 1]
- Test edge cases (empty data, insufficient data)
- Test pattern timestamp and index assignment

### Integration Tests (Future)

- End-to-end analysis with real OHLCV data
- Multi-timeframe alignment verification
- Context rule triggering validation

### Test Data

Synthetic candle data designed to trigger specific patterns:
```python
# Bullish engulfing test data
candles = [
    [100, 102, 98, 99],    # Red candle
    [98.5, 103, 98, 101],  # Green engulfing
]
```

## Performance Considerations

### Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Pattern Detection | O(n) | Single pass through candles |
| MA20 Calculation | O(n) | Rolling window |
| Multi-Timeframe | O(n * m) | n candles, m timeframes |
| Context Analysis | O(1) | Fixed number of rules |

### Memory Usage

- OHLCV Data: ~100 candles × 6 fields × 8 bytes = ~4.8KB per symbol/timeframe
- Pattern Results: ~5 patterns × 5 fields = ~200 bytes
- Total per analysis: <10KB

### Optimization Opportunities

1. **Caching:** Cache analysis results for recent candles
2. **Incremental Updates:** Only analyze new candles, not full history
3. **Batch Processing:** Analyze multiple symbols in parallel

## Error Handling

### Data Quality

- Empty DataFrame → Return empty result
- Insufficient data → Skip patterns requiring more candles
- Invalid OHLCV values → Log warning, skip candle

### Runtime Errors

- Database connection errors → Raise with clear message
- Pattern detection failures → Continue with partial results
- Configuration errors → Fail fast with validation error

## Future Enhancements

### Phase 2

1. **Volume Analysis:** Add volume confirmation to patterns
2. **RSI/MACD Integration:** Add momentum indicators
3. **Support/Resistance:** Automated S/R level detection
4. **Backtesting:** Historical performance validation

### Phase 3

1. **Machine Learning:** Pattern success rate prediction
2. **Portfolio Context:** Multi-symbol correlation analysis
3. **Risk Management:** Position sizing recommendations
4. **Alert Routing:** Smart notification based on confidence

## Configuration Reference

```python
Config(
    db_path="ohlcv.db",           # Database file path
    ma_period=20,                  # MA calculation period
    slope_threshold=0.001,         # Threshold for flat slope
    doji_threshold=0.01,           # Body/range ratio for doji
    hammer_threshold=0.3,          # Shadow ratio for hammer
    pattern_lookback=5,            # Days to check for context
    confidence_weights={           # Timeframe weights
        "weekly": 0.4,
        "daily": 0.3,
        "4h": 0.2,
        "1h": 0.1
    }
)
```

## Conclusion

This Analysis Engine provides a robust, modular foundation for context-aware trading signal analysis. The design prioritizes:

- **Transparency:** Every signal is explainable
- **Flexibility:** Modular architecture allows easy updates
- **Performance:** Efficient algorithms for real-time analysis
- **Accuracy:** Multi-factor confidence scoring reduces false positives

The engine is production-ready for integration with the TradingView Alert Agent system.
