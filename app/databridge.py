
import pandas as pd
from sqlalchemy import text
from typing import Dict, List, Union, Optional, Any, Callable
from datetime import datetime, date
import json
import logging
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataBridge:
    """
    A high-performance financial data query engine with multi-threading support
    for executing SQL queries across multiple databases.
    """
    
    def __init__(self, 
                 get_engine_func: Callable[[str], Any],
                 max_workers: int = 4,
                 auto_format: bool = True):
        """
        Initialize DataBridge with engine getter function.
        
        Args:
            get_engine_func: Function that takes engine name and returns SQLAlchemy engine
            max_workers: Maximum number of threads for parallel execution
            auto_format: Whether to automatically format DataFrames after query execution
        """
        self.get_engine_func = get_engine_func
        self.max_workers = max_workers
        self.auto_format = auto_format
        self._local = threading.local()
    
    @contextmanager
    def get_connection(self, engine_name: str):
        """Context manager for database connections with transaction support."""
        engine = self.get_engine_func(engine_name)
        conn = engine.begin()  # Use begin() for better transaction handling
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            conn.close()
    
    def _prepare_params(self, **kwargs) -> Dict[str, Any]:
        """
        Prepare and validate query parameters.
        
        Args:
            **kwargs: Query parameters including start_date, end_date, depart, asset_id, etc.
            
        Returns:
            Dictionary of prepared parameters
        """
        params = {}
        
        # Handle date parameters
        for date_param in ['start_date', 'end_date']:
            if date_param in kwargs:
                value = kwargs[date_param]
                if isinstance(value, str):
                    try:
                        params[date_param] = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            params[date_param] = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            params[date_param] = value
                elif isinstance(value, (datetime, date)):
                    params[date_param] = value
                else:
                    params[date_param] = value
        
        # Handle other parameters
        for param in ['depart', 'asset_id', 'symbol', 'portfolio_id', 'account_id']:
            if param in kwargs:
                params[param] = kwargs[param]
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in params:
                params[key] = value
        
        return params
    
    def _format_dataframe(self, df: pd.DataFrame, format_options: Dict[str, Any] = None) -> pd.DataFrame:
        """
        Apply formatting options to DataFrame.
        
        Args:
            df: Input DataFrame
            format_options: Dictionary of formatting options
            
        Returns:
            Formatted DataFrame
        """
        if df.empty:
            return df
        
        # Default formatting options
        default_options = {
            'uppercase_columns': False,
            'lowercase_columns': False,
            'snake_case_columns': False,
            'convert_date_columns': True,
            'strip_whitespace': True,
            'convert_numeric': True,
            'fill_na_numeric': None,  # Value to fill NaN in numeric columns
            'fill_na_string': '',     # Value to fill NaN in string columns
            'round_decimals': None,   # Number of decimal places for rounding
            'convert_boolean': True,  # Convert 1/0 to True/False
            'standardize_currency': False,  # Remove currency symbols
            'date_format': None,      # Specific date format to apply
            'remove_duplicates': False,
            'sort_by': None,         # Column name to sort by
            'sort_ascending': True
        }
        
        # Merge with user options
        if format_options:
            default_options.update(format_options)
        
        options = default_options
        df_formatted = df.copy()
        
        # Column name transformations
        if options['uppercase_columns']:
            df_formatted.columns = df_formatted.columns.str.upper()
        elif options['lowercase_columns']:
            df_formatted.columns = df_formatted.columns.str.lower()
        elif options['snake_case_columns']:
            df_formatted.columns = df_formatted.columns.str.replace(' ', '_').str.lower()
        
        # Strip whitespace from string columns
        if options['strip_whitespace']:
            string_cols = df_formatted.select_dtypes(include=['object']).columns
            for col in string_cols:
                df_formatted[col] = df_formatted[col].astype(str).str.strip()
        
        # Convert date columns
        if options['convert_date_columns']:
            # Auto-detect date columns by name patterns
            date_patterns = ['date', 'time', 'timestamp', 'created', 'updated', 'modified']
            potential_date_cols = [col for col in df_formatted.columns 
                                 if any(pattern in col.lower() for pattern in date_patterns)]
            
            for col in potential_date_cols:
                try:
                    df_formatted[col] = pd.to_datetime(df_formatted[col], errors='coerce')
                    if options['date_format']:
                        df_formatted[col] = df_formatted[col].dt.strftime(options['date_format'])
                except Exception as e:
                    logger.warning(f"Could not convert column '{col}' to datetime: {e}")
        
        # Convert numeric columns
        if options['convert_numeric']:
            for col in df_formatted.columns:
                if df_formatted[col].dtype == 'object':
                    # Try to convert to numeric
                    numeric_series = pd.to_numeric(df_formatted[col], errors='coerce')
                    if not numeric_series.isna().all():
                        df_formatted[col] = numeric_series
        
        # Handle currency columns
        if options['standardize_currency']:
            for col in df_formatted.columns:
                if df_formatted[col].dtype == 'object':
                    # Remove common currency symbols
                    if df_formatted[col].astype(str).str.contains(r'[\$€£¥₹]', na=False).any():
                        df_formatted[col] = df_formatted[col].astype(str).str.replace(r'[\$€£¥₹,]', '', regex=True)
                        df_formatted[col] = pd.to_numeric(df_formatted[col], errors='coerce')
        
        # Convert boolean columns
        if options['convert_boolean']:
            for col in df_formatted.columns:
                if df_formatted[col].dtype in ['int64', 'float64']:
                    unique_vals = df_formatted[col].dropna().unique()
                    if len(unique_vals) <= 2 and set(unique_vals).issubset({0, 1, 0.0, 1.0}):
                        df_formatted[col] = df_formatted[col].astype(bool)
        
        # Fill NaN values
        if options['fill_na_numeric'] is not None:
            numeric_cols = df_formatted.select_dtypes(include=['number']).columns
            df_formatted[numeric_cols] = df_formatted[numeric_cols].fillna(options['fill_na_numeric'])
        
        if options['fill_na_string']:
            string_cols = df_formatted.select_dtypes(include=['object']).columns
            df_formatted[string_cols] = df_formatted[string_cols].fillna(options['fill_na_string'])
        
        # Round decimal places
        if options['round_decimals'] is not None:
            numeric_cols = df_formatted.select_dtypes(include=['float']).columns
            df_formatted[numeric_cols] = df_formatted[numeric_cols].round(options['round_decimals'])
        
        # Remove duplicates
        if options['remove_duplicates']:
            df_formatted = df_formatted.drop_duplicates()
        
        # Sort DataFrame
        if options['sort_by'] and options['sort_by'] in df_formatted.columns:
            df_formatted = df_formatted.sort_values(
                by=options['sort_by'], 
                ascending=options['sort_ascending']
            )
        
        return df_formatted
    
    def execute_query(self, 
                     engine_name: str, 
                     query: str, 
                     format_options: Dict[str, Any] = None,
                     **kwargs) -> pd.DataFrame:
        """
        Execute a single query and return a DataFrame.
        
        Args:
            engine_name: Name of the database engine to use
            query: SQL query string
            format_options: Dictionary of DataFrame formatting options
            **kwargs: Query parameters (start_date, end_date, depart, asset_id, etc.)
            
        Returns:
            pandas DataFrame with query results
        """
        params = self._prepare_params(**kwargs)
        
        try:
            with self.get_connection(engine_name) as conn:
                logger.info(f"Executing query on engine '{engine_name}'")
                logger.debug(f"Query: {query}")
                logger.debug(f"Parameters: {params}")
                
                df = pd.read_sql_query(text(query), conn, params=params)
                logger.info(f"Query returned {len(df)} rows")
                
                # Apply formatting if enabled
                if self.auto_format or format_options:
                    df = self._format_dataframe(df, format_options)
                
                return df
                
        except Exception as e:
            logger.error(f"Error executing query on engine '{engine_name}': {str(e)}")
            raise
    
    def _execute_single_config(self, config: Dict[str, Any]) -> tuple[str, pd.DataFrame]:
        """
        Execute a single query configuration (used by threading).
        
        Args:
            config: Query configuration dictionary
            
        Returns:
            Tuple of (query_name, DataFrame)
        """
        name = config['name']
        engine_name = config['engine']
        query = config['query']
        
        # Extract format options
        format_options = config.get('format_options', None)
        
        # Extract parameters (everything except the required keys and format_options)
        params = {k: v for k, v in config.items() 
                 if k not in ['name', 'engine', 'query', 'format_options']}
        
        try:
            logger.info(f"Executing query: {name}")
            df = self.execute_query(engine_name, query, format_options, **params)
            return name, df
        except Exception as e:
            logger.error(f"Error in query '{name}': {str(e)}")
            return name, pd.DataFrame()  # Return empty DataFrame on error
    
    def execute_bulk_queries(self, 
                           query_configs: List[Dict[str, Any]],
                           multithread: bool = False) -> Dict[str, pd.DataFrame]:
        """
        Execute multiple queries and return a dictionary of DataFrames.
        
        Args:
            query_configs: List of dictionaries containing query configurations.
                          Each dict should have 'name', 'engine', 'query', and optional parameters.
            multithread: Whether to use multi-threading for parallel execution
                          
        Returns:
            Dictionary mapping query names to their resulting DataFrames
        """
        # Validate configurations
        for config in query_configs:
            if not isinstance(config, dict):
                raise ValueError("Each query config must be a dictionary")
            
            required_keys = ['name', 'engine', 'query']
            missing_keys = [key for key in required_keys if key not in config]
            if missing_keys:
                raise ValueError(f"Missing required keys in query config: {missing_keys}")
        
        if not multithread or len(query_configs) <= 2:
            # Sequential execution for small configs or when multithread is disabled
            results = {}
            for config in query_configs:
                name, df = self._execute_single_config(config)
                results[name] = df
            return results
        
        # Parallel execution for larger configs
        logger.info(f"Executing {len(query_configs)} queries in parallel with {self.max_workers} workers")
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all queries
            future_to_name = {
                executor.submit(self._execute_single_config, config): config['name']
                for config in query_configs
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_name):
                try:
                    name, df = future.result()
                    results[name] = df
                except Exception as e:
                    query_name = future_to_name[future]
                    logger.error(f"Query '{query_name}' failed: {str(e)}")
                    results[query_name] = pd.DataFrame()
        
        return results
    
    def execute_from_json(self, 
                         json_input: Union[str, List[Dict[str, Any]]],
                         multithread: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Execute queries from JSON input with optional multi-threading.
        
        Args:
            json_input: JSON string or list of dictionaries containing query configurations
            multithread: Whether to use multi-threading for parallel execution
            
        Returns:
            Dictionary mapping query names to their resulting DataFrames
        """
        if isinstance(json_input, str):
            try:
                query_configs = json.loads(json_input)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON input: {str(e)}")
        else:
            query_configs = json_input
        
        if not isinstance(query_configs, list):
            raise ValueError("JSON input must be a list of query configurations")
        
        # Automatically use multi-threading for large configs
        use_multithread = multithread and len(query_configs) > 3
        
        return self.execute_bulk_queries(query_configs, multithread=use_multithread)
    
    def get_sample_config(self) -> List[Dict[str, Any]]:
        """
        Get a sample configuration for reference.
        
        Returns:
            List of sample query configurations
        """
        return [
            {
                "name": "portfolio_performance",
                "engine": "main_db",
                "query": """
                    SELECT date, symbol, price, volume 
                    FROM stock_prices 
                    WHERE date BETWEEN :start_date AND :end_date
                    AND symbol = :asset_id
                """,
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "asset_id": "AAPL",
                "format_options": {
                    "uppercase_columns": True,
                    "convert_date_columns": True,
                    "round_decimals": 2
                }
            },
            {
                "name": "department_trades",
                "engine": "trading_db",
                "query": """
                    SELECT trade_id, symbol, quantity, price, trade_date 
                    FROM trades 
                    WHERE department = :depart 
                    AND trade_date >= :start_date
                """,
                "depart": "equity",
                "start_date": "2024-01-01",
                "format_options": {
                    "snake_case_columns": True,
                    "standardize_currency": True,
                    "sort_by": "trade_date"
                }
            },
            {
                "name": "risk_metrics",
                "engine": "risk_db",
                "query": """
                    SELECT portfolio_id, var_95, var_99, expected_shortfall
                    FROM risk_metrics
                    WHERE calculation_date = :calc_date
                """,
                "calc_date": "2024-12-31",
                "format_options": {
                    "round_decimals": 4,
                    "fill_na_numeric": 0,
                    "remove_duplicates": True
                }
            }
        ]
    
    def get_formatting_options(self) -> Dict[str, Any]:
        """
        Get all available formatting options with descriptions.
        
        Returns:
            Dictionary of formatting options and their descriptions
        """
        return {
            "uppercase_columns": "Convert all column names to uppercase",
            "lowercase_columns": "Convert all column names to lowercase", 
            "snake_case_columns": "Convert column names to snake_case",
            "convert_date_columns": "Auto-detect and convert date columns to datetime",
            "strip_whitespace": "Remove leading/trailing whitespace from string columns",
            "convert_numeric": "Auto-detect and convert numeric columns",
            "fill_na_numeric": "Value to fill NaN in numeric columns (e.g., 0)",
            "fill_na_string": "Value to fill NaN in string columns (e.g., '')",
            "round_decimals": "Number of decimal places for rounding (e.g., 2)",
            "convert_boolean": "Convert 1/0 columns to True/False",
            "standardize_currency": "Remove currency symbols and convert to numeric",
            "date_format": "Specific date format string (e.g., '%Y-%m-%d')",
            "remove_duplicates": "Remove duplicate rows",
            "sort_by": "Column name to sort by",
            "sort_ascending": "Sort in ascending order (True) or descending (False)"
        }
    
    def benchmark_queries(self, 
                         query_configs: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Benchmark query execution times for performance optimization.
        
        Args:
            query_configs: List of query configurations to benchmark
            
        Returns:
            Dictionary mapping query names to execution times in seconds
        """
        import time
        
        results = {}
        
        for config in query_configs:
            name = config['name']
            start_time = time.time()
            
            try:
                self._execute_single_config(config)
                execution_time = time.time() - start_time
                results[name] = execution_time
                logger.info(f"Query '{name}' executed in {execution_time:.2f} seconds")
            except Exception as e:
                logger.error(f"Query '{name}' failed during benchmark: {str(e)}")
                results[name] = -1.0  # Indicate failure
        
        return results


# Convenience functions for minimal user code
def create_databridge(get_engine_func: Callable[[str], Any], 
                     max_workers: int = 4,
                     auto_format: bool = True) -> DataBridge:
    """
    Create a new DataBridge instance.
    
    Args:
        get_engine_func: Function that takes engine name and returns SQLAlchemy engine
        max_workers: Maximum number of threads for parallel execution
        auto_format: Whether to automatically format DataFrames
        
    Returns:
        DataBridge instance
    """
    return DataBridge(get_engine_func, max_workers, auto_format)

def quick_query(engine_name: str, 
                query: str, 
                get_engine_func: Callable[[str], Any],
                format_options: Dict[str, Any] = None,
                **kwargs) -> pd.DataFrame:
    """
    Execute a quick single query with minimal setup.
    
    Args:
        engine_name: Name of the database engine
        query: SQL query string
        get_engine_func: Function to get engine by name
        format_options: Dictionary of DataFrame formatting options
        **kwargs: Query parameters
        
    Returns:
        pandas DataFrame with results
    """
    bridge = DataBridge(get_engine_func)
    return bridge.execute_query(engine_name, query, format_options, **kwargs)

def bulk_query(query_configs: List[Dict[str, Any]], 
               get_engine_func: Callable[[str], Any],
               multithread: bool = True) -> Dict[str, pd.DataFrame]:
    """
    Execute bulk queries with minimal setup and optional multi-threading.
    
    Args:
        query_configs: List of query configurations
        get_engine_func: Function to get engine by name
        multithread: Whether to use multi-threading
        
    Returns:
        Dictionary of DataFrames
    """
    bridge = DataBridge(get_engine_func)
    return bridge.execute_bulk_queries(query_configs, multithread=multithread)

def json_query(json_input: Union[str, List[Dict[str, Any]]], 
               get_engine_func: Callable[[str], Any],
               multithread: bool = True) -> Dict[str, pd.DataFrame]:
    """
    Execute queries from JSON with minimal setup and optional multi-threading.
    
    Args:
        json_input: JSON string or list of dictionaries
        get_engine_func: Function to get engine by name
        multithread: Whether to use multi-threading
        
    Returns:
        Dictionary of DataFrames
    """
    bridge = DataBridge(get_engine_func)
    return bridge.execute_from_json(json_input, multithread=multithread)


# Example usage and test functions
if __name__ == "__main__":
    # Example get_engine function (user would provide this)
    def get_engine(engine_name: str):
        from sqlalchemy import create_engine
        engine_map = {
            'main_db': create_engine('sqlite:///financial_data.db'),
            'trading_db': create_engine('sqlite:///trading_data.db'),
            'risk_db': create_engine('sqlite:///risk_data.db')
        }
        return engine_map.get(engine_name)
    
    # Initialize DataBridge
    bridge = create_databridge(get_engine, max_workers=6)
    
    # Example 1: Single query with formatting
    try:
        df = bridge.execute_query(
            engine_name='main_db',
            query="""
                SELECT * FROM prices 
                WHERE date BETWEEN :start_date AND :end_date 
                AND symbol = :asset_id
            """,
            format_options={
                'uppercase_columns': True,
                'convert_date_columns': True,
                'round_decimals': 2
            },
            start_date='2024-01-01',
            end_date='2024-12-31',
            asset_id='AAPL'
        )
        print(f"Single query returned {len(df)} rows with formatting")
        print(f"Column names: {list(df.columns)}")
    except Exception as e:
        print(f"Single query example failed: {e}")
    
    # Example 1.5: Show formatting options
    try:
        formatting_options = bridge.get_formatting_options()
        print("\nAvailable formatting options:")
        for option, description in formatting_options.items():
            print(f"  {option}: {description}")
    except Exception as e:
        print(f"Formatting options example failed: {e}")
    
    # Example 2: Multi-threaded bulk queries with different formatting
    large_config = [
        {
            "name": f"formatted_query_{i}",
            "engine": "main_db",
            "query": f"SELECT symbol, price, volume, trade_date FROM prices WHERE symbol = :asset_id LIMIT 10",
            "asset_id": ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"][i % 5],
            "format_options": {
                "uppercase_columns": i % 2 == 0,  # Alternate formatting
                "convert_date_columns": True,
                "round_decimals": 2,
                "sort_by": "trade_date" if i % 3 == 0 else None
            }
        }
        for i in range(10)
    ]
    
    try:
        # Multi-threaded execution
        results = bridge.execute_bulk_queries(large_config, multithread=True)
        print(f"Multi-threaded bulk queries returned {len(results)} DataFrames")
        
        # Sequential execution for comparison
        results_seq = bridge.execute_bulk_queries(large_config, multithread=False)
        print(f"Sequential bulk queries returned {len(results_seq)} DataFrames")
        
    except Exception as e:
        print(f"Bulk query example failed: {e}")
    
    # Example 3: JSON input with formatting options
    json_config = '''
    [
        {
            "name": "portfolio_summary",
            "engine": "main_db",
            "query": "SELECT symbol, AVG(price) as avg_price, SUM(volume) as total_volume FROM prices GROUP BY symbol LIMIT 5",
            "format_options": {
                "uppercase_columns": true,
                "round_decimals": 2,
                "sort_by": "avg_price",
                "sort_ascending": false
            }
        },
        {
            "name": "trading_volume",
            "engine": "trading_db", 
            "query": "SELECT symbol, SUM(volume) as total_volume, trade_date FROM trades GROUP BY symbol LIMIT 5",
            "format_options": {
                "snake_case_columns": true,
                "convert_date_columns": true,
                "fill_na_numeric": 0
            }
        }
    ]
    '''
    
    try:
        json_results = bridge.execute_from_json(json_config, multithread=True)
        print(f"JSON multi-threaded queries returned {len(json_results)} DataFrames")
    except Exception as e:
        print(f"JSON query example failed: {e}")
    
    # Example 4: Super minimal convenience functions with formatting
    try:
        # One-liner for single queries with formatting
        df = quick_query(
            'main_db', 
            'SELECT symbol, price, volume FROM prices LIMIT 3',
            get_engine,
            format_options={
                'uppercase_columns': True,
                'round_decimals': 2
            }
        )
        print(f"Quick formatted query returned {len(df)} rows")
        print(f"Columns: {list(df.columns)}")
        
        # One-liner for multi-threaded bulk queries with formatting
        results = bulk_query(large_config[:3], get_engine, multithread=True)
        print(f"Quick multi-threaded bulk query returned {len(results)} DataFrames")
        
        # Show sample of formatted results
        for name, df in list(results.items())[:2]:
            print(f"  {name} columns: {list(df.columns)}")
        
    except Exception as e:
        print(f"Quick query examples failed: {e}")
    
    # Example 5: Demonstrate different formatting options
    try:
        sample_query = "SELECT 'Apple Inc.' as company_name, 150.25 as stock_price, '2024-01-15' as trade_date, 1 as is_active"
        
        # Test different formatting options
        formatting_tests = [
            ("uppercase_columns", {"uppercase_columns": True}),
            ("snake_case_columns", {"snake_case_columns": True}),
            ("date_conversion", {"convert_date_columns": True}),
            ("boolean_conversion", {"convert_boolean": True}),
            ("decimal_rounding", {"round_decimals": 1})
        ]
        
        print("\nFormatting examples:")
        for test_name, options in formatting_tests:
            try:
                df = bridge.execute_query('main_db', sample_query, format_options=options)
                print(f"  {test_name}: {list(df.columns)} | Types: {df.dtypes.to_dict()}")
            except Exception as e:
                print(f"  {test_name}: Failed - {e}")
        
    except Exception as e:
        print(f"Formatting examples failed: {e}")
    
    # Example 5: Benchmark queries
    try:
        sample_config = bridge.get_sample_config()[:2]  # Use first 2 for testing
        benchmark_results = bridge.benchmark_queries(sample_config)
        print("\nBenchmark results:")
        for name, time_taken in benchmark_results.items():
            if time_taken > 0:
                print(f"  {name}: {time_taken:.2f} seconds")
            else:
                print(f"  {name}: Failed")
                
        # Show sample config with formatting
        print("\nSample configuration with formatting options:")
        for config in sample_config:
            print(f"  {config['name']}: {config.get('format_options', {})}")
                
    except Exception as e:
        print(f"Benchmark example failed: {e}")
Made with
Claude
