from typing import Union, List, Optional, Dict, Any
import holidays
import sqlite3
from functools import lru_cache
import warnings

# Type aliases
DateLike = Union[str, datetime, date, pd.Timestamp]

# Global configuration
_DEFAULT_CALENDAR = 'NYSE'
_DB_CONNECTION = None
_CUSTOM_CALENDARS = {}
_MARKET_CALENDARS = {}

# Initialize market calendars lazily
def _get_market_calendar(name: str):
    """Lazy load market calendars"""
    global _MARKET_CALENDARS
    if name not in _MARKET_CALENDARS:
        try:
            from pandas_market_calendars import get_calendar
            _MARKET_CALENDARS[name] = get_calendar(name)
        except ImportError:
            warnings.warn("pandas_market_calendars not available, using numpy busday")
            _MARKET_CALENDARS[name] = None
    return _MARKET_CALENDARS[name]

# Country holidays - lazy loaded
@lru_cache(maxsize=10)
def _get_country_holidays(country: str):
    """Get country holidays with caching"""
    country_map = {
        'US': holidays.US(),
        'UK': holidays.UK(), 
        'CA': holidays.Canada(),
        'DE': holidays.Germany(),
        'FR': holidays.France(),
        'JP': holidays.Japan(),
        'AU': holidays.Australia(),
        'IN': holidays.India(),
        'SG': holidays.Singapore(),
    }
    return country_map.get(country.upper())

# Configuration functions
def set_default_calendar(calendar: str) -> None:
    """Set default calendar globally"""
    global _DEFAULT_CALENDAR
    _DEFAULT_CALENDAR = calendar

def set_db_connection(connection) -> None:
    """Set database connection globally"""
    global _DB_CONNECTION
    _DB_CONNECTION = connection

def add_calendar(name: str, country: str = None, holidays_list: List[DateLike] = None, 
                weekends: List[int] = None) -> None:
    """Add custom calendar"""
    global _CUSTOM_CALENDARS
    _CUSTOM_CALENDARS[name] = {
        'weekends': weekends or [5, 6],
        'holidays': set(pd.to_datetime(holidays_list or []).date),
        'country_holidays': _get_country_holidays(country) if country else None
    }

@lru_cache(maxsize=100)
def load_holidays(calendar: str, table: str = 'holidays') -> List[date]:
    """Load holidays from database with caching"""
    if not _DB_CONNECTION:
        raise ValueError("Database connection not set")
    
    query = f"SELECT holiday_date FROM {table} WHERE calendar_name = ? ORDER BY holiday_date"
    df = pd.read_sql_query(query, _DB_CONNECTION, params=[calendar])
    return pd.to_datetime(df['holiday_date']).dt.date.tolist()

# Core business day functions
def is_bday(dates: DateLike, cal: str = None) -> Union[bool, pd.Series]:
    """Check if business day(s)"""
    cal = cal or _DEFAULT_CALENDAR
    dates = pd.to_datetime(dates)
    
    # Try market calendar first
    market_cal = _get_market_calendar(cal)
    if market_cal:
        if isinstance(dates, pd.Timestamp):
            return market_cal.valid_days(dates, dates).shape[0] > 0
        else:
            valid_days = market_cal.valid_days(dates.min(), dates.max())
            return dates.isin(valid_days)
    
    # Try custom calendar
    if cal in _CUSTOM_CALENDARS:
        config = _CUSTOM_CALENDARS[cal]
        is_weekday = ~dates.dt.dayofweek.isin(config['weekends'])
        is_not_holiday = ~dates.dt.date.isin(config['holidays'])
        if config['country_holidays']:
            country_holidays = pd.Series([d in config['country_holidays'] for d in dates.dt.date])
            is_not_holiday &= ~country_holidays
        return is_weekday & is_not_holiday
    
    # Default numpy busday
    if isinstance(dates, pd.Timestamp):
        return np.is_busday(dates.date())
    else:
        return pd.Series(np.is_busday(dates.dt.date.values))

def next_bday(dates: DateLike, cal: str = None) -> Union[pd.Timestamp, pd.Series]:
    """Next business day(s)"""
    cal = cal or _DEFAULT_CALENDAR
    dates = pd.to_datetime(dates)
    
    # Use numpy for speed when possible
    market_cal = _get_market_calendar(cal)
    if not market_cal or cal not in _CUSTOM_CALENDARS:
        if isinstance(dates, pd.Timestamp):
            return pd.Timestamp(np.busday_offset(dates.date(), 1, roll='forward'))
        else:
            return pd.to_datetime(np.busday_offset(dates.dt.date.values, 1, roll='forward'))
    
    # Market calendar logic for complex calendars
    if isinstance(dates, pd.Timestamp):
        valid_days = market_cal.valid_days(dates, dates + timedelta(days=30))
        next_days = valid_days[valid_days > dates]
        return next_days[0] if len(next_days) > 0 else None
    else:
        result = []
        for d in dates:
            valid_days = market_cal.valid_days(d, d + timedelta(days=30))
            next_days = valid_days[valid_days > d]
            result.append(next_days[0] if len(next_days) > 0 else None)
        return pd.Series(result)

def prev_bday(dates: DateLike, cal: str = None) -> Union[pd.Timestamp, pd.Series]:
    """Previous business day(s)"""
    dates = pd.to_datetime(dates)
    if isinstance(dates, pd.Timestamp):
        return pd.Timestamp(np.busday_offset(dates.date(), -1, roll='backward'))
    else:
        return pd.to_datetime(np.busday_offset(dates.dt.date.values, -1, roll='backward'))

def add_bdays(dates: DateLike, days: int, cal: str = None) -> Union[pd.Timestamp, pd.Series]:
    """Add business days"""
    dates = pd.to_datetime(dates)
    
    # Use numpy for standard business days (fastest)
    if cal is None or cal == _DEFAULT_CALENDAR:
        if isinstance(dates, pd.Timestamp):
            return pd.Timestamp(np.busday_offset(dates.date(), days))
        else:
            return pd.to_datetime(np.busday_offset(dates.dt.date.values, days))
    
    # Market calendar for complex cases
    market_cal = _get_market_calendar(cal or _DEFAULT_CALENDAR)
    if market_cal and abs(days) > 10:
        if isinstance(dates, pd.Timestamp):
            if days > 0:
                end_date = dates + timedelta(days=days*2)
                valid_days = market_cal.valid_days(dates, end_date)
                valid_days = valid_days[valid_days > dates]
                return valid_days[min(days-1, len(valid_days)-1)] if len(valid_days) >= days else None
            else:
                start_date = dates + timedelta(days=days*2)
                valid_days = market_cal.valid_days(start_date, dates)
                valid_days = valid_days[valid_days < dates]
                return valid_days[max(0, len(valid_days) + days)] if len(valid_days) >= abs(days) else None
    
    # Fallback to numpy
    if isinstance(dates, pd.Timestamp):
        return pd.Timestamp(np.busday_offset(dates.date(), days))
    else:
        return pd.to_datetime(np.busday_offset(dates.dt.date.values, days))

def bdays_between(start: DateLike, end: DateLike, cal: str = None) -> int:
    """Count business days between dates"""
    start, end = pd.to_datetime(start), pd.to_datetime(end)
    
    market_cal = _get_market_calendar(cal or _DEFAULT_CALENDAR)
    if market_cal:
        return len(market_cal.valid_days(start, end))
    else:
        return np.busday_count(start.date(), end.date())

def bday_range(start: DateLike, end: DateLike, cal: str = None) -> pd.DatetimeIndex:
    """Business day range"""
    start, end = pd.to_datetime(start), pd.to_datetime(end)
    
    market_cal = _get_market_calendar(cal or _DEFAULT_CALENDAR)
    if market_cal:
        return market_cal.valid_days(start, end)
    else:
        return pd.bdate_range(start, end)

# Period functions
def add_days(dates: DateLike, days: int) -> Union[pd.Timestamp, pd.Series]:
    """Add calendar days"""
    return pd.to_datetime(dates) + pd.Timedelta(days=days)

def add_weeks(dates: DateLike, weeks: int) -> Union[pd.Timestamp, pd.Series]:
    """Add weeks"""
    return pd.to_datetime(dates) + pd.Timedelta(weeks=weeks)

def add_months(dates: DateLike, months: int) -> Union[pd.Timestamp, pd.Series]:
    """Add months"""
    return pd.to_datetime(dates) + pd.DateOffset(months=months)

def add_quarters(dates: DateLike, quarters: int) -> Union[pd.Timestamp, pd.Series]:
    """Add quarters"""
    return pd.to_datetime(dates) + pd.DateOffset(months=quarters*3)

def add_years(dates: DateLike, years: int) -> Union[pd.Timestamp, pd.Series]:
    """Add years"""
    return pd.to_datetime(dates) + pd.DateOffset(years=years)

# Period boundaries
def month_end(dates: DateLike) -> Union[pd.Timestamp, pd.Series]:
    """End of month"""
    return pd.to_datetime(dates) + pd.offsets.MonthEnd(0)

def month_start(dates: DateLike) -> Union[pd.Timestamp, pd.Series]:
    """Start of month"""
    dates = pd.to_datetime(dates)
    return dates - pd.offsets.Day(dates.dt.day - 1)

def quarter_end(dates: DateLike) -> Union[pd.Timestamp, pd.Series]:
    """End of quarter"""
    return pd.to_datetime(dates) + pd.offsets.QuarterEnd(0)

def quarter_start(dates: DateLike) -> Union[pd.Timestamp, pd.Series]:
    """Start of quarter"""
    dates = pd.to_datetime(dates)
    quarter = dates.dt.quarter
    return pd.to_datetime(dates.dt.year.astype(str) + '-' + 
                         ((quarter - 1) * 3 + 1).astype(str) + '-01')

def year_end(dates: DateLike) -> Union[pd.Timestamp, pd.Series]:
    """End of year"""
    return pd.to_datetime(dates) + pd.offsets.YearEnd(0)

def year_start(dates: DateLike) -> Union[pd.Timestamp, pd.Series]:
    """Start of year"""
    dates = pd.to_datetime(dates)
    return pd.to_datetime(dates.dt.year.astype(str) + '-01-01')

def week_end(dates: DateLike) -> Union[pd.Timestamp, pd.Series]:
    """End of week (Sunday)"""
    dates = pd.to_datetime(dates)
    return dates + pd.to_timedelta(6 - dates.dt.dayofweek, unit='D')

def week_start(dates: DateLike) -> Union[pd.Timestamp, pd.Series]:
    """Start of week (Monday)"""
    dates = pd.to_datetime(dates)
    return dates - pd.to_timedelta(dates.dt.dayofweek, unit='D')

# Financial specific functions
def imm_dates(year: int) -> List[pd.Timestamp]:
    """IMM dates - 3rd Wednesday of Mar/Jun/Sep/Dec"""
    dates = []
    for month in [3, 6, 9, 12]:
        first = pd.Timestamp(year, month, 1)
        # Find first Wednesday, then add 2 weeks for 3rd
        first_wed = first + pd.Timedelta(days=(2 - first.weekday()) % 7)
        third_wed = first_wed + pd.Timedelta(weeks=2)
        dates.append(third_wed)
    return dates

def roll_date(dates: DateLike, convention: str = 'following', cal: str = None) -> Union[pd.Timestamp, pd.Series]:
    """Roll dates by business day convention"""
    dates = pd.to_datetime(dates)
    
    if convention == 'following':
        mask = ~is_bday(dates, cal)
        if isinstance(dates, pd.Timestamp):
            return next_bday(dates, cal) if mask else dates
        else:
            result = dates.copy()
            result[mask] = next_bday(dates[mask], cal)
            return result
    
    elif convention == 'preceding':
        mask = ~is_bday(dates, cal)
        if isinstance(dates, pd.Timestamp):
            return prev_bday(dates, cal) if mask else dates
        else:
            result = dates.copy()
            result[mask] = prev_bday(dates[mask], cal)
            return result
    
    elif convention == 'modified_following':
        following = roll_date(dates, 'following', cal)
        if isinstance(dates, pd.Timestamp):
            return roll_date(dates, 'preceding', cal) if following.month != dates.month else following
        else:
            mask = following.dt.month != dates.dt.month
            result = following.copy()
            result[mask] = roll_date(dates[mask], 'preceding', cal)
            return result
    
    else:
        raise ValueError(f"Unknown convention: {convention}")

# Convenience generators
def month_ends(start: DateLike, periods: int) -> pd.DatetimeIndex:
    """Generate month end dates"""
    return pd.date_range(start=pd.to_datetime(start), periods=periods, freq='M')

def quarter_ends(start: DateLike, periods: int) -> pd.DatetimeIndex:
    """Generate quarter end dates"""
    return pd.date_range(start=pd.to_datetime(start), periods=periods, freq='Q')

def year_ends(start: DateLike, periods: int) -> pd.DatetimeIndex:
    """Generate year end dates"""
    return pd.date_range(start=pd.to_datetime(start), periods=periods, freq='Y')

def bday_series(start: DateLike, periods: int, cal: str = None) -> pd.DatetimeIndex:
    """Generate business day series"""
    market_cal = _get_market_calendar(cal or _DEFAULT_CALENDAR)
    if market_cal:
        start_date = pd.to_datetime(start)
        end_estimate = start_date + pd.Timedelta(days=periods * 2)  # Conservative estimate
        valid_days = market_cal.valid_days(start_date, end_estimate)
        return valid_days[:periods]
    else:
        return pd.bdate_range(start=start, periods=periods)

# Utility functions
def today() -> pd.Timestamp:
    """Today's date"""
    return pd.Timestamp.now().normalize()

def now() -> pd.Timestamp:
    """Current timestamp"""
    return pd.Timestamp.now()

def is_weekend(dates: DateLike) -> Union[bool, pd.Series]:
    """Check if weekend"""
    dates = pd.to_datetime(dates)
    if isinstance(dates, pd.Timestamp):
        return dates.weekday() >= 5
    else:
        return dates.dt.weekday >= 5

def weekday(dates: DateLike) -> Union[int, pd.Series]:
    """Get weekday (0=Monday, 6=Sunday)"""
    dates = pd.to_datetime(dates)
    if isinstance(dates, pd.Timestamp):
        return dates.weekday()
    else:
        return dates.dt.weekday

def days_in_month(dates: DateLike) -> Union[int, pd.Series]:
    """Days in month"""
    dates = pd.to_datetime(dates)
    if isinstance(dates, pd.Timestamp):
        return dates.days_in_month
    else:
        return dates.dt.days_in_month

def cal_info(calendar: str = None) -> Dict[str, Any]:
    """Get calendar information"""
    cal = calendar or _DEFAULT_CALENDAR
    market_cal = _get_market_calendar(cal)
    
    if not market_cal:
        return {'calendar': cal, 'type': 'numpy_busday'}
    
    current_year = datetime.now().year
    holidays_list = market_cal.holidays()
    upcoming = holidays_list[holidays_list >= pd.Timestamp.now()][:5]
    
    return {
        'calendar': cal,
        'timezone': str(market_cal.tz),
        'upcoming_holidays': upcoming.tolist(),
        'trading_days_remaining': len(market_cal.valid_days(
            pd.Timestamp.now(), pd.Timestamp(current_year, 12, 31)
        ))
    }

# Aliases for even shorter names
bd = is_bday          # business day check
nbd = next_bday      # next business day
pbd = prev_bday      # previous business day
abd = add_bdays      # add business days
bdr = bday_range     # business day range
me = month_end       # month end
ms = month_start     # month start
qe = quarter_end     # quarter end
qs = quarter_start   # quarter start
ye = year_end        # year end
ys = year_start      # year start

# Example usage
if __name__ == "__main__":
    # Setup
    set_default_calendar('NYSE')
    
    # Basic usage
    today_date = today()
    print(f"Today: {today_date.date()}")
    print(f"Is business day: {bd(today_date)}")
    print(f"Next business day: {nbd(today_date).date()}")
    print(f"Add 5 business days: {abd(today_date, 5).date()}")
    print(f"Month end: {me(today_date).date()}")
    print(f"Quarter end: {qe(today_date).date()}")
    
    # Vectorized operations
    dates = pd.date_range('2024-01-01', '2024-01-10')
    print(f"Business days: {bd(dates).sum()}")
    print(f"Next business days: {nbd(dates)[:3].date}")
    
    # Period operations
    print(f"Business days this month: {bdays_between(ms(today_date), me(today_date))}")
    
    # IMM dates
    imm_2024 = imm_dates(2024)
    print(f"IMM dates 2024: {[d.date() for d in imm_2024]}")
    
    # Calendar info
    info = cal_info('NYSE')
    print(f"Trading days remaining: {info.get('trading_days_remaining', 'N/A')}")
