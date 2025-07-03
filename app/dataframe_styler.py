import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Callable
import re
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import warnings
import base64
import io
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.figure import Figure

class FinancialDataFrameStyler:
    """
    A comprehensive utility for styling pandas DataFrames for financial reports.
    Automatically detects column types and applies appropriate formatting.
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialize the styler with a DataFrame.
        
        Args:
            df: The pandas DataFrame to style
        """
        self.df = df.copy()
        self.styled_df = None
        self._column_mappings = self._detect_column_types()
        
        # Default styling configurations
        self.config = {
            'currency_symbol': '$',
            'currency_precision': 2,
            'percentage_precision': 2,
            'number_precision': 2,
            'date_format': '%Y-%m-%d',
            'negative_color': '#FF6B6B',
            'positive_color': '#51CF66',
            'neutral_color': '#868E96',
            'header_bg_color': '#495057',
            'header_text_color': 'white',
            'alternate_row_color': '#F8F9FA',
            'border_color': '#DEE2E6',
            'font_family': 'Arial, sans-serif',
            'font_size': '12px'
        }
    
    def _detect_column_types(self) -> Dict[str, List[str]]:
        """
        Automatically detect column types based on names and data.
        
        Returns:
            Dictionary mapping column types to column names
        """
        mappings = {
            'currency': [],
            'percentage': [],
            'date': [],
            'number': [],
            'text': []
        }
        
        # Keywords for different column types
        currency_keywords = ['price', 'cost', 'revenue', 'profit', 'loss', 'expense', 
                           'income', 'salary', 'wage', 'amount', 'value', 'cash', 
                           'balance', 'capital', 'investment', 'debt', 'equity']
        
        percentage_keywords = ['rate', 'ratio', 'percent', 'margin', 'growth', 
                             'return', 'yield', 'change', 'pct', '%']
        
        date_keywords = ['date', 'time', 'day', 'month', 'year', 'period', 
                        'timestamp', 'created', 'updated', 'start', 'end']
        
        for col in self.df.columns:
            col_lower = col.lower()
            
            # Check if it's a datetime column
            if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                mappings['date'].append(col)
            # Check for date keywords
            elif any(keyword in col_lower for keyword in date_keywords):
                mappings['date'].append(col)
            # Check for currency keywords
            elif any(keyword in col_lower for keyword in currency_keywords):
                mappings['currency'].append(col)
            # Check for percentage keywords or values between 0-1 or 0-100
            elif (any(keyword in col_lower for keyword in percentage_keywords) or 
                  (pd.api.types.is_numeric_dtype(self.df[col]) and 
                   self.df[col].dropna().between(0, 1).all()) or
                  (pd.api.types.is_numeric_dtype(self.df[col]) and 
                   self.df[col].dropna().between(0, 100).all() and 
                   '%' in col_lower)):
                mappings['percentage'].append(col)
            # Check if it's numeric
            elif pd.api.types.is_numeric_dtype(self.df[col]):
                mappings['number'].append(col)
            # Default to text
            else:
                mappings['text'].append(col)
        
        return mappings
    
    def update_config(self, **kwargs):
        """
        Update styling configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        self.config.update(kwargs)
        return self
    
    def set_column_types(self, column_types: Dict[str, List[str]]):
        """
        Manually set column type mappings.
        
        Args:
            column_types: Dictionary mapping column types to column names
        """
        self._column_mappings.update(column_types)
        return self
    
    def add_column_type(self, column_type: str, columns: Union[str, List[str]]):
        """
        Add columns to a specific type.
        
        Args:
            column_type: Type of column ('currency', 'percentage', 'date', 'number', 'text')
            columns: Column name(s) to add
        """
        if isinstance(columns, str):
            columns = [columns]
        
        if column_type not in self._column_mappings:
            self._column_mappings[column_type] = []
        
        self._column_mappings[column_type].extend(columns)
        return self
    
    def _format_currency(self, val):
        """Format currency values."""
        if pd.isna(val):
            return ''
        try:
            symbol = self.config['currency_symbol']
            precision = self.config['currency_precision']
            if val < 0:
                return f"({symbol}{abs(val):,.{precision}f})"
            return f"{symbol}{val:,.{precision}f}"
        except:
            return str(val)
    
    def _format_percentage(self, val):
        """Format percentage values."""
        if pd.isna(val):
            return ''
        try:
            precision = self.config['percentage_precision']
            # If value is between 0-1, assume it's already a ratio
            if 0 <= abs(val) <= 1:
                return f"{val * 100:.{precision}f}%"
            # If value is larger, assume it's already a percentage
            return f"{val:.{precision}f}%"
        except:
            return str(val)
    
    def _format_number(self, val):
        """Format numeric values."""
        if pd.isna(val):
            return ''
        try:
            precision = self.config['number_precision']
            return f"{val:,.{precision}f}"
        except:
            return str(val)
    
    def _format_date(self, val):
        """Format date values."""
        if pd.isna(val):
            return ''
        try:
            if isinstance(val, str):
                val = pd.to_datetime(val)
            return val.strftime(self.config['date_format'])
        except:
            return str(val)
    
    def _highlight_negative(self, val):
        """Style negative values."""
        try:
            if pd.isna(val) or not isinstance(val, (int, float)):
                return ''
            if val < 0:
                return f'color: {self.config["negative_color"]}; font-weight: bold;'
            elif val > 0:
                return f'color: {self.config["positive_color"]};'
            else:
                return f'color: {self.config["neutral_color"]};'
        except:
            return ''
    
    def _get_base_styles(self):
        """Get base CSS styles for the table."""
        return [
            {
                'selector': 'table',
                'props': [
                    ('border-collapse', 'collapse'),
                    ('margin', '25px 0'),
                    ('font-size', self.config['font_size']),
                    ('font-family', self.config['font_family']),
                    ('min-width', '400px'),
                    ('border-radius', '5px 5px 0 0'),
                    ('overflow', 'hidden'),
                    ('box-shadow', '0 0 20px rgba(0, 0, 0, 0.15)')
                ]
            },
            {
                'selector': 'th',
                'props': [
                    ('background-color', self.config['header_bg_color']),
                    ('color', self.config['header_text_color']),
                    ('font-weight', 'bold'),
                    ('padding', '12px 15px'),
                    ('text-align', 'left'),
                    ('border-bottom', f'2px solid {self.config["border_color"]}')
                ]
            },
            {
                'selector': 'td',
                'props': [
                    ('padding', '12px 15px'),
                    ('border-bottom', f'1px solid {self.config["border_color"]}')
                ]
            },
            {
                'selector': 'tr:nth-child(even)',
                'props': [
                    ('background-color', self.config['alternate_row_color'])
                ]
            },
            {
                'selector': 'tr:hover',
                'props': [
                    ('background-color', '#F1F3F4'),
                    ('cursor', 'pointer')
                ]
            }
        ]
    
    def style(self, 
              highlight_negatives: bool = True,
              apply_formats: bool = True,
              custom_formatters: Optional[Dict[str, Callable]] = None,
              custom_styles: Optional[List[Dict]] = None) -> pd.io.formats.style.Styler:
        """
        Apply comprehensive styling to the DataFrame.
        
        Args:
            highlight_negatives: Whether to highlight negative values
            apply_formats: Whether to apply number/currency/date formatting
            custom_formatters: Custom formatting functions for specific columns
            custom_styles: Additional CSS styles to apply
            
        Returns:
            Styled DataFrame
        """
        styler = self.df.style
        
        # Apply base styles
        base_styles = self._get_base_styles()
        if custom_styles:
            base_styles.extend(custom_styles)
        styler = styler.set_table_styles(base_styles)
        
        # Apply formatting
        if apply_formats:
            formatters = {}
            
            # Currency formatting
            for col in self._column_mappings.get('currency', []):
                if col in self.df.columns:
                    formatters[col] = self._format_currency
            
            # Percentage formatting
            for col in self._column_mappings.get('percentage', []):
                if col in self.df.columns:
                    formatters[col] = self._format_percentage
            
            # Number formatting
            for col in self._column_mappings.get('number', []):
                if col in self.df.columns:
                    formatters[col] = self._format_number
            
            # Date formatting
            for col in self._column_mappings.get('date', []):
                if col in self.df.columns:
                    formatters[col] = self._format_date
            
            # Apply custom formatters
            if custom_formatters:
                formatters.update(custom_formatters)
            
            if formatters:
                styler = styler.format(formatters)
        
        # Highlight negative values
        if highlight_negatives:
            numeric_cols = (self._column_mappings.get('currency', []) + 
                          self._column_mappings.get('number', []) + 
                          self._column_mappings.get('percentage', []))
            
            for col in numeric_cols:
                if col in self.df.columns:
                    styler = styler.applymap(self._highlight_negative, subset=[col])
        
        # Set caption
        styler = styler.set_caption("Financial Data Report")
        
        self.styled_df = styler
        return styler
    
    def to_html(self, 
                file_path: Optional[str] = None,
                include_plotly: bool = False,
                plots: Optional[List[go.Figure]] = None,
                title: str = "Financial Report",
                email_friendly: bool = False) -> str:
        """
        Generate HTML report with styled DataFrame and optional plots.
        
        Args:
            file_path: Path to save HTML file (optional)
            include_plotly: Whether to include Plotly plots (ignored if email_friendly=True)
            plots: List of Plotly figures to include
            title: Report title
            email_friendly: Generate email-compatible HTML with inline images
            
        Returns:
            HTML string
        """
        if self.styled_df is None:
            self.style()
        
        # For email-friendly version, generate static images instead of Plotly
        if email_friendly:
            include_plotly = False
            if plots:
                # Convert Plotly figures to matplotlib and create base64 images
                plot_images = self._convert_plots_to_images(plots)
            else:
                plot_images = []
        else:
            plot_images = []
        
        # Get table HTML with email-friendly styles if needed
        if email_friendly:
            table_html = self._get_email_friendly_table_html()
        else:
            table_html = self.styled_df.to_html()
        
        # Create appropriate styles based on email compatibility
        css_styles = self._get_email_styles() if email_friendly else self._get_web_styles()
        
        # Create full HTML document
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            {'<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>' if include_plotly else ''}
            <style>
                {css_styles}
            </style>
        </head>
        <body>
            <div class="report-container">
                <h1 class="report-title">{title}</h1>
                
                <div class="table-container">
                    {table_html}
                </div>
                
                {self._generate_image_html(plot_images) if email_friendly and plot_images else ''}
                {'<div id="plots-container"></div>' if include_plotly and plots else ''}
                
                <div class="timestamp">
                    Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </div>
            </div>
            
            {'<script>' + self._generate_plotly_js(plots) + '</script>' if include_plotly and plots else ''}
        </body>
        </html>
        """
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_template)
            print(f"HTML report saved to: {file_path}")
        
        return html_template
    
    def _generate_plotly_js(self, plots: List[go.Figure]) -> str:
        """Generate JavaScript code for Plotly plots."""
        if not plots:
            return ""
        
        js_code = """
        const plotsContainer = document.getElementById('plots-container');
        """
        
        for i, fig in enumerate(plots):
            plot_div_id = f"plot-{i}"
            js_code += f"""
            const plotDiv{i} = document.createElement('div');
            plotDiv{i}.id = '{plot_div_id}';
            plotDiv{i}.className = 'plot-container';
            plotsContainer.appendChild(plotDiv{i});
            
            Plotly.newPlot('{plot_div_id}', {fig.to_json()});
            """
        
        return js_code
    
    def _convert_plots_to_images(self, plots: List[go.Figure], 
                               width: int = 800, height: int = 500) -> List[str]:
        """
        Convert Plotly figures to base64 encoded images for email compatibility.
        
        Args:
            plots: List of Plotly figures
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            List of base64 encoded image strings
        """
        image_strings = []
        
        # Set matplotlib style for better looking plots
        plt.style.use('default')
        sns.set_palette("husl")
        
        for i, fig in enumerate(plots):
            try:
                # Extract data from Plotly figure
                fig_data = fig.to_dict()
                
                # Create matplotlib figure
                matplotlib_fig = Figure(figsize=(width/100, height/100), dpi=100)
                ax = matplotlib_fig.add_subplot(111)
                
                # Convert based on plot type
                if fig_data.get('data'):
                    trace = fig_data['data'][0]
                    plot_type = trace.get('type', 'scatter')
                    
                    if plot_type == 'bar':
                        ax.bar(trace.get('x', []), trace.get('y', []))
                        ax.set_xlabel(trace.get('name', 'X'))
                        ax.set_ylabel('Values')
                        if trace.get('x') and len(trace['x']) > 5:
                            ax.tick_params(axis='x', rotation=45)
                    
                    elif plot_type == 'scatter' and trace.get('mode') == 'lines':
                        ax.plot(trace.get('x', []), trace.get('y', []))
                        ax.set_xlabel('X')
                        ax.set_ylabel('Values')
                    
                    elif plot_type == 'pie':
                        ax.pie(trace.get('values', []), labels=trace.get('labels', []), 
                              autopct='%1.1f%%')
                    
                    else:
                        # Default scatter plot
                        ax.scatter(trace.get('x', []), trace.get('y', []))
                        ax.set_xlabel('X')
                        ax.set_ylabel('Y')
                
                # Set title
                if fig_data.get('layout', {}).get('title'):
                    title = fig_data['layout']['title']
                    if isinstance(title, dict):
                        title = title.get('text', f'Chart {i+1}')
                    ax.set_title(title)
                else:
                    ax.set_title(f'Chart {i+1}')
                
                # Improve layout
                matplotlib_fig.tight_layout()
                
                # Convert to base64
                img_buffer = io.BytesIO()
                matplotlib_fig.savefig(img_buffer, format='png', bbox_inches='tight', 
                                     facecolor='white', edgecolor='none')
                img_buffer.seek(0)
                img_str = base64.b64encode(img_buffer.read()).decode()
                image_strings.append(img_str)
                
                # Clean up
                plt.close(matplotlib_fig)
                
            except Exception as e:
                print(f"Warning: Could not convert plot {i+1} to image: {e}")
                continue
        
        return image_strings
    
    def _generate_image_html(self, image_strings: List[str]) -> str:
        """Generate HTML for embedded base64 images."""
        if not image_strings:
            return ""
        
        html = '<div class="plots-section">\n'
        for i, img_str in enumerate(image_strings):
            html += f'''
            <div class="plot-container">
                <img src="data:image/png;base64,{img_str}" 
                     alt="Chart {i+1}" 
                     style="max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; border-radius: 5px;">
            </div>
            '''
        html += '</div>\n'
        return html
    
    def _get_email_styles(self) -> str:
        """Get email-compatible CSS styles (inline-friendly)."""
        return f"""
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .report-container {{
                background-color: white;
                padding: 20px;
                border: 1px solid #ddd;
                max-width: 800px;
                margin: 0 auto;
            }}
            .report-title {{
                color: {self.config['header_bg_color']};
                text-align: center;
                margin-bottom: 20px;
                font-size: 24px;
                font-weight: bold;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
                font-size: 14px;
            }}
            th {{
                background-color: {self.config['header_bg_color']};
                color: white;
                font-weight: bold;
                padding: 10px 8px;
                text-align: left;
                border: 1px solid #ddd;
            }}
            td {{
                padding: 8px;
                border: 1px solid #ddd;
                text-align: left;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .plot-container {{
                text-align: center;
                margin: 20px 0;
            }}
            .timestamp {{
                text-align: right;
                color: #666;
                font-size: 11px;
                margin-top: 15px;
                font-style: italic;
            }}
            .plots-section {{
                margin: 20px 0;
            }}
        """
    
    def _get_web_styles(self) -> str:
        """Get full web-compatible CSS styles."""
        return f"""
            body {{
                font-family: {self.config['font_family']};
                margin: 40px;
                background-color: #f5f5f5;
            }}
            .report-container {{
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
            }}
            .report-title {{
                color: {self.config['header_bg_color']};
                text-align: center;
                margin-bottom: 30px;
                font-size: 28px;
                font-weight: bold;
            }}
            .plot-container {{
                margin: 30px 0;
                text-align: center;
            }}
            .table-container {{
                overflow-x: auto;
                margin: 20px 0;
            }}
            .timestamp {{
                text-align: right;
                color: #666;
                font-size: 12px;
                margin-top: 20px;
            }}
            table {{
                border-collapse: collapse;
                margin: 25px 0;
                font-size: {self.config['font_size']};
                font-family: {self.config['font_family']};
                min-width: 400px;
                border-radius: 5px 5px 0 0;
                overflow: hidden;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
            }}
            th {{
                background-color: {self.config['header_bg_color']};
                color: {self.config['header_text_color']};
                font-weight: bold;
                padding: 12px 15px;
                text-align: left;
                border-bottom: 2px solid {self.config['border_color']};
            }}
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid {self.config['border_color']};
            }}
            tr:nth-child(even) {{
                background-color: {self.config['alternate_row_color']};
            }}
            tr:hover {{
                background-color: #F1F3F4;
                cursor: pointer;
            }}
        """
    
    def _get_email_friendly_table_html(self) -> str:
        """Generate email-friendly table HTML with inline styles."""
        if self.styled_df is None:
            self.style()
        
        # Create a simplified version for email
        df_copy = self.df.copy()
        
        # Apply formatting manually
        formatters = {}
        
        # Currency formatting
        for col in self._column_mappings.get('currency', []):
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].apply(self._format_currency)
        
        # Percentage formatting
        for col in self._column_mappings.get('percentage', []):
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].apply(self._format_percentage)
        
        # Number formatting
        for col in self._column_mappings.get('number', []):
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].apply(self._format_number)
        
        # Date formatting
        for col in self._column_mappings.get('date', []):
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].apply(self._format_date)
        
        # Generate HTML with inline styles
        html = '<table style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif;">\n'
        
        # Header
        html += '<thead>\n<tr>\n'
        for col in df_copy.columns:
            html += f'<th style="background-color: {self.config["header_bg_color"]}; color: white; padding: 10px 8px; border: 1px solid #ddd; text-align: left;">{col}</th>\n'
        html += '</tr>\n</thead>\n'
        
        # Body
        html += '<tbody>\n'
        for idx, row in df_copy.iterrows():
            bg_color = '#f9f9f9' if idx % 2 == 0 else 'white'
            html += f'<tr style="background-color: {bg_color};">\n'
            for col in df_copy.columns:
                value = row[col]
                cell_style = 'padding: 8px; border: 1px solid #ddd;'
                
                # Add color for negative numbers
                if col in (self._column_mappings.get('currency', []) + 
                          self._column_mappings.get('number', []) + 
                          self._column_mappings.get('percentage', [])):
                    try:
                        original_val = self.df.loc[idx, col]
                        if pd.notna(original_val) and original_val < 0:
                            cell_style += f' color: {self.config["negative_color"]}; font-weight: bold;'
                        elif pd.notna(original_val) and original_val > 0:
                            cell_style += f' color: {self.config["positive_color"]};'
                    except:
                        pass
                
                html += f'<td style="{cell_style}">{value}</td>\n'
            html += '</tr>\n'
        html += '</tbody>\n</table>\n'
        
        return html
    
    def create_email_report(self, 
                          file_path: Optional[str] = None,
                          title: str = "Financial Report",
                          include_charts: bool = True,
                          chart_types: List[str] = ['bar', 'line']) -> str:
        """
        Create an email-friendly report with embedded images.
        
        Args:
            file_path: Path to save HTML file
            title: Report title
            include_charts: Whether to include charts
            chart_types: Types of charts to include
            
        Returns:
            Email-friendly HTML string
        """
        plots = []
        if include_charts:
            plots = self.create_summary_plots(plot_types=chart_types, max_categories=8)
        
        return self.to_html(
            file_path=file_path,
            title=title,
            plots=plots if include_charts else None,
            email_friendly=True
        )
    
    def create_summary_plots(self, 
                           plot_types: List[str] = ['bar', 'line', 'pie'],
                           max_categories: int = 10) -> List[go.Figure]:
        """
        Create summary plots based on the DataFrame data.
        
        Args:
            plot_types: Types of plots to create
            max_categories: Maximum number of categories for categorical plots
            
        Returns:
            List of Plotly figures
        """
        plots = []
        
        # Get numeric columns for plotting
        numeric_cols = (self._column_mappings.get('currency', []) + 
                       self._column_mappings.get('number', []))
        
        if not numeric_cols:
            return plots
        
        # Bar chart for categorical vs numeric data
        if 'bar' in plot_types:
            text_cols = self._column_mappings.get('text', [])
            if text_cols and numeric_cols:
                text_col = text_cols[0]
                numeric_col = numeric_cols[0]
                
                # Limit categories
                df_plot = self.df.copy()
                if df_plot[text_col].nunique() > max_categories:
                    top_categories = df_plot[text_col].value_counts().head(max_categories).index
                    df_plot = df_plot[df_plot[text_col].isin(top_categories)]
                
                fig = px.bar(df_plot, x=text_col, y=numeric_col, 
                           title=f"{numeric_col} by {text_col}")
                fig.update_layout(xaxis_tickangle=-45)
                plots.append(fig)
        
        # Line chart for time series data
        if 'line' in plot_types:
            date_cols = self._column_mappings.get('date', [])
            if date_cols and numeric_cols:
                date_col = date_cols[0]
                numeric_col = numeric_cols[0]
                
                df_plot = self.df.copy()
                df_plot[date_col] = pd.to_datetime(df_plot[date_col])
                df_plot = df_plot.sort_values(date_col)
                
                fig = px.line(df_plot, x=date_col, y=numeric_col,
                            title=f"{numeric_col} Over Time")
                plots.append(fig)
        
        # Pie chart for categorical data
        if 'pie' in plot_types:
            text_cols = self._column_mappings.get('text', [])
            if text_cols:
                text_col = text_cols[0]
                
                # Create value counts
                value_counts = self.df[text_col].value_counts().head(max_categories)
                
                fig = px.pie(values=value_counts.values, names=value_counts.index,
                           title=f"Distribution of {text_col}")
                plots.append(fig)
        
        return plots
    
    def print_column_mappings(self):
        """Print the detected column type mappings."""
        print("Detected Column Type Mappings:")
        print("=" * 40)
        for col_type, columns in self._column_mappings.items():
            if columns:
                print(f"{col_type.capitalize()}: {', '.join(columns)}")
        print()

# Example usage and utility functions
def create_sample_financial_data():
    """Create sample financial data for testing."""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=50, freq='D')
    
    data = {
        'Date': dates,
        'Company': np.random.choice(['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'], 50),
        'Stock_Price': np.random.uniform(100, 500, 50),
        'Volume': np.random.randint(1000000, 10000000, 50),
        'Revenue': np.random.uniform(-1000000, 5000000, 50),
        'Profit_Margin': np.random.uniform(-0.1, 0.3, 50),
        'Growth_Rate': np.random.uniform(-20, 50, 50),
        'Market_Cap': np.random.uniform(1e9, 1e12, 50),
        'P/E_Ratio': np.random.uniform(5, 50, 50),
        'Sector': np.random.choice(['Technology', 'Healthcare', 'Finance'], 50)
    }
    
    return pd.DataFrame(data)

# Example usage
if __name__ == "__main__":
    # Create sample data
    df = create_sample_financial_data()
    
    # Initialize styler
    styler = FinancialDataFrameStyler(df)
    
    # Print detected column mappings
    styler.print_column_mappings()
    
    # Customize configuration
    styler.update_config(
        currency_symbol='$',
        negative_color='#FF4444',
        positive_color='#44AA44'
    )
    
    # Style the DataFrame
    styled_df = styler.style()
    
    # Create plots
    plots = styler.create_summary_plots(['bar', 'line', 'pie'])
    
    # Generate HTML report
    html_report = styler.to_html(
        file_path='financial_report.html',
        include_plotly=True,
        plots=plots,
        title='Sample Financial Analysis Report'
    )
    
    # Generate email-friendly report
    email_report = styler.create_email_report(
        file_path='financial_report_email.html',
        title='Sample Financial Analysis Report',
        include_charts=True,
        chart_types=['bar', 'pie']
    )
    
    print("Financial DataFrame Styler is ready to use!")
    print("Generated files:")
    print("- financial_report.html (full web version with Plotly)")
    print("- financial_report_email.html (email-compatible with static images)")
