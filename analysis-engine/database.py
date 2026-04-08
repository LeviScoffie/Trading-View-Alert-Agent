"""
SQLite database module for OHLCV data storage.
Handles data persistence and retrieval for analysis.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict
import json

from models import OHLCV, Timeframe, Config


class OHLCVDatabase:
    """SQLite database manager for OHLCV data."""
    
    def __init__(self, db_path: str = "ohlcv.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, timestamp)
                )
            """)
            
            # Index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ohlcv_lookup 
                ON ohlcv(symbol, timeframe, timestamp)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, timestamp)
                )
            """)
            
            conn.commit()
    
    def store_ohlcv(self, symbol: str, timeframe: Timeframe, data: List[OHLCV]):
        """Store OHLCV data for a symbol and timeframe."""
        with sqlite3.connect(self.db_path) as conn:
            for candle in data:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO ohlcv 
                    (symbol, timeframe, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        timeframe.value,
                        candle.timestamp.isoformat(),
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume
                    )
                )
            conn.commit()
    
    def get_ohlcv(
        self, 
        symbol: str, 
        timeframe: Timeframe, 
        limit: int = 100,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Retrieve OHLCV data as a pandas DataFrame.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe enum
            limit: Number of candles to retrieve
            end_time: Optional end time for historical queries
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ?
        """
        params = [symbol, timeframe.value]
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            return df
        
        # Convert timestamp and sort
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        return df
    
    def get_multi_timeframe_data(
        self, 
        symbol: str, 
        end_time: Optional[datetime] = None,
        config: Optional[Config] = None
    ) -> Dict[Timeframe, pd.DataFrame]:
        """
        Retrieve data for all supported timeframes.
        
        Returns:
            Dictionary mapping timeframe to DataFrame
        """
        result = {}
        limits = {
            Timeframe.WEEKLY: 52,   # 1 year of weekly data
            Timeframe.DAILY: 90,    # 3 months of daily data
            Timeframe.FOUR_HOUR: 168,  # 1 month of 4H data
            Timeframe.ONE_HOUR: 168    # 1 week of 1H data
        }
        
        for timeframe in Timeframe:
            df = self.get_ohlcv(symbol, timeframe, limit=limits[timeframe], end_time=end_time)
            if not df.empty:
                result[timeframe] = df
        
        return result
    
    def get_latest_candle(self, symbol: str, timeframe: Timeframe) -> Optional[OHLCV]:
        """Get the most recent candle for a symbol/timeframe."""
        df = self.get_ohlcv(symbol, timeframe, limit=1)
        
        if df.empty:
            return None
        
        row = df.iloc[0]
        return OHLCV(
            timestamp=row['timestamp'],
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=row['volume']
        )
    
    def store_analysis_result(self, symbol: str, timeframe: Timeframe, 
                             timestamp: datetime, result: dict):
        """Cache analysis result."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analysis_cache 
                (symbol, timeframe, timestamp, result)
                VALUES (?, ?, ?, ?)
                """,
                (symbol, timeframe.value, timestamp.isoformat(), json.dumps(result))
            )
            conn.commit()
    
    def get_cached_analysis(self, symbol: str, timeframe: Timeframe,
                           timestamp: datetime) -> Optional[dict]:
        """Retrieve cached analysis result."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT result FROM analysis_cache
                WHERE symbol = ? AND timeframe = ? AND timestamp = ?
                """,
                (symbol, timeframe.value, timestamp.isoformat())
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None
    
    def delete_old_data(self, days: int = 365):
        """Delete data older than specified days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM ohlcv WHERE timestamp < ?", (cutoff,))
            conn.execute("DELETE FROM analysis_cache WHERE timestamp < ?", (cutoff,))
            conn.commit()
    
    def get_symbols(self) -> List[str]:
        """Get list of all symbols in database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT DISTINCT symbol FROM ohlcv")
            return [row[0] for row in cursor.fetchall()]
    
    def get_timeframes_for_symbol(self, symbol: str) -> List[str]:
        """Get list of timeframes available for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT timeframe FROM ohlcv WHERE symbol = ?",
                (symbol,)
            )
            return [row[0] for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection (no-op for SQLite)."""
        pass