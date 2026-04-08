"""SQLite database operations for TradingView alerts."""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from config import settings

logger = logging.getLogger(__name__)


class AlertDatabase:
    """Manages SQLite database operations for TradingView alerts."""
    
    def __init__(self, db_path: str = None):
        """Initialize database with the given path."""
        self.db_path = db_path or settings.database_path
        self._ensure_directory()
        self._init_database()
    
    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL,
                    message TEXT,
                    alert_time TEXT,
                    raw_payload TEXT NOT NULL,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_symbol 
                ON alerts(symbol)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_received_at 
                ON alerts(received_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alerts_processed 
                ON alerts(processed)
            """)
            
            # Create behavior_logs table for manual observations
            conn.execute("""
                CREATE TABLE IF NOT EXISTS behavior_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    timeframe TEXT,
                    note TEXT,
                    source TEXT DEFAULT 'manual'
                )
            """)
            
            # Create indexes for behavior_logs
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_behavior_symbol 
                ON behavior_logs(symbol)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_behavior_timestamp 
                ON behavior_logs(timestamp DESC)
            """)
            
            logger.info(f"Database initialized at {self.db_path}")
    
    def store_alert(
        self,
        symbol: str,
        price: Optional[float],
        message: Optional[str],
        alert_time: Optional[str],
        raw_payload: Dict[str, Any]
    ) -> int:
        """Store a new alert in the database.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            price: Price value from the alert
            message: Alert message text
            alert_time: Timestamp from TradingView
            raw_payload: Complete JSON payload as dict
            
        Returns:
            The ID of the inserted alert
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO alerts (symbol, price, message, alert_time, raw_payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    price,
                    message,
                    alert_time,
                    json.dumps(raw_payload)
                )
            )
            alert_id = cursor.lastrowid
            logger.info(f"Stored alert {alert_id} for {symbol}")
            return alert_id
    
    def get_alert(self, alert_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific alert by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM alerts WHERE id = ?",
                (alert_id,)
            ).fetchone()
            
            if row:
                return dict(row)
            return None
    
    def get_recent_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent alerts, ordered by received time."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM alerts 
                ORDER BY received_at DESC 
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_alerts_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get alerts for a specific symbol."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM alerts 
                WHERE symbol = ?
                ORDER BY received_at DESC 
                LIMIT ?
                """,
                (symbol.upper(), limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_as_processed(self, alert_id: int) -> bool:
        """Mark an alert as processed."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE alerts SET processed = TRUE WHERE id = ?",
                (alert_id,)
            )
            return cursor.rowcount > 0
    
    def get_unprocessed_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get alerts that haven't been processed yet."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM alerts 
                WHERE processed = FALSE
                ORDER BY received_at ASC 
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM alerts"
            ).fetchone()[0]
            
            unprocessed = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE processed = FALSE"
            ).fetchone()[0]
            
            # Get unique symbols count
            symbols = conn.execute(
                "SELECT COUNT(DISTINCT symbol) FROM alerts"
            ).fetchone()[0]
            
            # Get most recent alert time
            latest = conn.execute(
                "SELECT MAX(received_at) FROM alerts"
            ).fetchone()[0]
            
            # Get behavior logs count
            behavior_count = conn.execute(
                "SELECT COUNT(*) FROM behavior_logs"
            ).fetchone()[0]
            
            return {
                "total_alerts": total,
                "unprocessed_alerts": unprocessed,
                "unique_symbols": symbols,
                "latest_alert": latest,
                "behavior_logs": behavior_count
            }
    
    def store_behavior_log(
        self,
        symbol: str,
        timeframe: Optional[str] = None,
        note: Optional[str] = None,
        source: str = 'manual'
    ) -> int:
        """Store a manual behavior observation log.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            timeframe: Chart timeframe (e.g., "4H", "1D")
            note: Observation note/description
            source: Source of the log (default: 'manual')
            
        Returns:
            The ID of the inserted behavior log
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO behavior_logs (symbol, timeframe, note, source)
                VALUES (?, ?, ?, ?)
                """,
                (symbol.upper(), timeframe, note, source)
            )
            log_id = cursor.lastrowid
            logger.info(f"Stored behavior log {log_id} for {symbol}")
            return log_id
    
    def get_recent_behavior_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent behavior logs, ordered by timestamp."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM behavior_logs 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_behavior_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get behavior logs for a specific symbol."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM behavior_logs 
                WHERE symbol = ?
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (symbol.upper(), limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_behavior_attention_heatmap(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get attention heatmap showing most observed symbols.
        
        Args:
            days: Number of days to look back (default: 7)
            
        Returns:
            List of symbols with observation counts
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    symbol,
                    COUNT(*) as observation_count,
                    MAX(timestamp) as last_observed,
                    GROUP_CONCAT(DISTINCT timeframe) as timeframes
                FROM behavior_logs 
                WHERE timestamp >= datetime('now', '-? days')
                GROUP BY symbol
                ORDER BY observation_count DESC
                """,
                (days,)
            )
            return [dict(row) for row in cursor.fetchall()]


# Global database instance
db = AlertDatabase()