"""
Timezone Utilities Module

Handles EST/EDT timezone conversions with automatic DST detection.
Provides helper functions for timezone-aware datetime operations.
"""

from datetime import datetime
from typing import Optional
import pytz

from config import TIMEZONE


class TimezoneManager:
    """
    Manages timezone conversions for the scheduler.
    
    Uses pytz for proper EST/EDT handling with automatic DST transitions.
    All times are stored in UTC internally but displayed/configured in EST/EDT.
    """
    
    def __init__(self, timezone: str = TIMEZONE):
        """
        Initialize the timezone manager.
        
        Args:
            timezone: The target timezone (default: America/New_York for EST/EDT)
        """
        self.timezone_name = timezone
        self.tz = pytz.timezone(timezone)
        self.utc = pytz.UTC
    
    def now(self) -> datetime:
        """
        Get current time in the target timezone.
        
        Returns:
            Timezone-aware datetime in EST/EDT
        """
        return datetime.now(self.tz)
    
    def now_utc(self) -> datetime:
        """
        Get current time in UTC.
        
        Returns:
            Timezone-aware datetime in UTC
        """
        return datetime.now(self.utc)
    
    def to_local(self, dt: datetime) -> datetime:
        """
        Convert a datetime to the target timezone.
        
        Args:
            dt: Datetime to convert (naive or timezone-aware)
            
        Returns:
            Timezone-aware datetime in EST/EDT
        """
        if dt.tzinfo is None:
            # Assume UTC if no timezone info
            dt = self.utc.localize(dt)
        return dt.astimezone(self.tz)
    
    def to_utc(self, dt: datetime) -> datetime:
        """
        Convert a datetime to UTC.
        
        Args:
            dt: Datetime to convert (naive or timezone-aware)
            
        Returns:
            Timezone-aware datetime in UTC
        """
        if dt.tzinfo is None:
            # Assume local timezone if no timezone info
            dt = self.tz.localize(dt)
        return dt.astimezone(self.utc)
    
    def is_dst(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if DST is active for a given datetime.
        
        Args:
            dt: Datetime to check (default: current time)
            
        Returns:
            True if DST is active, False otherwise
        """
        if dt is None:
            dt = self.now()
        elif dt.tzinfo is None:
            dt = self.tz.localize(dt)
        else:
            dt = dt.astimezone(self.tz)
        
        return bool(dt.dst())
    
    def get_utc_offset(self, dt: Optional[datetime] = None) -> int:
        """
        Get UTC offset in hours for a given datetime.
        
        Args:
            dt: Datetime to check (default: current time)
            
        Returns:
            UTC offset in hours (e.g., -5 for EST, -4 for EDT)
        """
        if dt is None:
            dt = self.now()
        elif dt.tzinfo is None:
            dt = self.tz.localize(dt)
        else:
            dt = dt.astimezone(self.tz)
        
        offset = dt.utcoffset()
        if offset is None:
            return 0
        return int(offset.total_seconds() // 3600)
    
    def format_with_timezone(self, dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
        """
        Format a datetime with timezone abbreviation.
        
        Args:
            dt: Datetime to format
            fmt: Format string (default includes timezone)
            
        Returns:
            Formatted datetime string
        """
        if dt.tzinfo is None:
            dt = self.tz.localize(dt)
        return dt.strftime(fmt)
    
    def get_next_dst_transition(self) -> Optional[datetime]:
        """
        Get the next DST transition date.
        
        Returns:
            Datetime of the next DST transition, or None if not determinable
        """
        now = self.now()
        year = now.year
        
        # DST starts second Sunday in March at 2:00 AM
        # DST ends first Sunday in November at 2:00 AM
        
        # Find second Sunday in March
        march_1 = self.tz.localize(datetime(year, 3, 1, 2, 0))
        days_until_sunday = (6 - march_1.weekday()) % 7
        second_sunday_march = march_1 + __import__('datetime').timedelta(days=days_until_sunday + 7)
        
        # Find first Sunday in November
        nov_1 = self.tz.localize(datetime(year, 11, 1, 2, 0))
        days_until_sunday = (6 - nov_1.weekday()) % 7
        first_sunday_nov = nov_1 + __import__('datetime').timedelta(days=days_until_sunday)
        
        if now < second_sunday_march:
            return second_sunday_march
        elif now < first_sunday_nov:
            return first_sunday_nov
        else:
            # Next transition is next year's March
            march_1_next = self.tz.localize(datetime(year + 1, 3, 1, 2, 0))
            days_until_sunday = (6 - march_1_next.weekday()) % 7
            return march_1_next + __import__('datetime').timedelta(days=days_until_sunday + 7)
    
    def localize(self, dt: datetime, is_dst: Optional[bool] = None) -> datetime:
        """
        Localize a naive datetime to the target timezone.
        
        Args:
            dt: Naive datetime to localize
            is_dst: Whether DST is active (None for ambiguous times)
            
        Returns:
            Timezone-aware datetime
        """
        if dt.tzinfo is not None:
            return dt.astimezone(self.tz)
        return self.tz.localize(dt, is_dst=is_dst)


# Global timezone manager instance
tz_manager = TimezoneManager()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def now() -> datetime:
    """Get current time in EST/EDT."""
    return tz_manager.now()

def now_utc() -> datetime:
    """Get current time in UTC."""
    return tz_manager.now_utc()

def to_local(dt: datetime) -> datetime:
    """Convert datetime to EST/EDT."""
    return tz_manager.to_local(dt)

def to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC."""
    return tz_manager.to_utc(dt)

def is_dst(dt: Optional[datetime] = None) -> bool:
    """Check if DST is active."""
    return tz_manager.is_dst(dt)

def get_utc_offset(dt: Optional[datetime] = None) -> int:
    """Get UTC offset in hours."""
    return tz_manager.get_utc_offset(dt)

def format_est(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """Format datetime with EST/EDT timezone."""
    return tz_manager.format_with_timezone(dt, fmt)


def get_last_day_of_month(year: int, month: int) -> int:
    """
    Get the last day of a given month.
    
    Args:
        year: The year
        month: The month (1-12)
        
    Returns:
        The last day of the month (28-31)
    """
    import calendar
    return calendar.monthrange(year, month)[1]


def get_next_monthly_run_date(current_date: Optional[datetime] = None) -> datetime:
    """
    Calculate the next monthly report run date (last day of current/next month).
    
    Args:
        current_date: Reference date (default: now)
        
    Returns:
        Datetime of the next monthly report run
    """
    if current_date is None:
        current_date = now()
    
    # Get last day of current month
    last_day = get_last_day_of_month(current_date.year, current_date.month)
    
    # If today is the last day and it's before 5 PM, run today
    if current_date.day == last_day and current_date.hour < 17:
        return current_date.replace(hour=17, minute=0, second=0, microsecond=0)
    
    # Otherwise, run on the last day of next month
    if current_date.month == 12:
        next_year = current_date.year + 1
        next_month = 1
    else:
        next_year = current_date.year
        next_month = current_date.month + 1
    
    last_day_next = get_last_day_of_month(next_year, next_month)
    return current_date.replace(
        year=next_year,
        month=next_month,
        day=last_day_next,
        hour=17,
        minute=0,
        second=0,
        microsecond=0
    )
