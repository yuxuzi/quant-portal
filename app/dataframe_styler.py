"""
Professional Email Report Library - Comprehensive solution for quantitative finance teams.
Combines intelligent DataFrame styling with email report generation and plotly chart embedding.
"""

import uuid
import base64
import io
import os
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np

try:
    import plotly.graph_objects as go
    import plotly.express as px
    import plotly.io as pio
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


@dataclass
class EmailConfig:
    """Email configuration for reports."""
    sender: str
    recipients: List[str]
    subject: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    reply_to: Optional[str] = None


@dataclass
class StyleConfig:
    """Professional styling configuration."""
    currency_symbol: str = '$'
    currency_precision: int = 2
    percentage_precision: int = 2
    number_precision: int = 2
    date_format: str = '%Y-%m-%d'
    
    # Colors
    negative_color: str = '#FF6B6B'
    positive_color: str = '#51CF66' 
    neutral_color: str = '#868E96'
    header_bg_color: str = '#2c3e50'
    header_text_color: str = 'white'
    alternate_row_color: str = '#F8F9FA'
    border_color: str = '#DEE2E6'
    
    # Typography
    font_family: str = 'Arial, sans-serif'
    font_size: str = '12px'
    
    # Email specific
    email_max_width: str = '800px'
    component_margin: str = '20px 0'
    component_padding: str = '15px'


class FinancialDataFrameStyler:
    """Intelligent DataFrame styling with automatic column type detection."""
    
    def __init__(self, df: pd.DataFrame, config: StyleConfig = None):
        self.df = df.copy()
        self.config = config or StyleConfig()
        self._column_mappings = self._detect_column_types()
    
    def _detect_column_types(self) -> Dict[str, List[str]]:
        """Automatically detect financial column types."""
        mappings = {
            'currency': [], 'percentage': [], 'date': [], 'number': [], 'text': []
        }
        
        # Financial keywords for classification
        keywords = {
            'currency': ['price', 'cost', 'revenue', 'profit', 'loss', 'expense', 'income', 
                        'salary', 'wage', 'amount', 'value', 'cash', 'balance', 'capital', 
                        'investment', 'debt', 'equity', 'pnl', 'p&l', 'notional'],
            'percentage': ['rate', 'ratio', 'percent', 'margin', 'growth', 'return', 'yield', 
                          'change', 'pct', '%', 'vol', 'volatility', 'sharpe', 'correlation'],
            'date': ['date', 'time', 'day', 'month', 'year', 'period', 'timestamp', 
                    'created', 'updated', 'start', 'end', 'expiry', 'maturity']
        }
        
        for col in self.df.columns:
            col_lower = col.lower().replace('_', ' ').replace('-', ' ')
            
            # Check datetime columns first
            if pd.api.types.is_datetime64_any_dtype(self.df[col]):
                mappings['date'].append(col)
            elif any(kw in col_lower for kw in keywords['date']):
                mappings['date'].append(col)
            elif any(kw in col_lower for kw in keywords['currency']):
                mappings['currency'].append(col)
            elif (any(kw in col_lower for kw in keywords['percentage']) or 
                  self._is_percentage_column(col)):
                mappings['percentage'].append(col)
            elif pd.api.types.is_numeric_dtype(self.df[col]):
                mappings['number'].append(col)
            else:
                mappings['text'].append(col)
        
        return mappings
    
    def _is_percentage_column(self, col: str) -> bool:
        """Check if column contains percentage-like data."""
        if not pd.api.types.is_numeric_dtype(self.df[col]):
            return False
        
        values = self.df[col].dropna()
        if len(values) == 0:
            return False
            
        # Check if values are in 0-1 range (likely ratios)
        if values.between(0, 1).all() and values.max() < 1:
            return True
            
        # Check if values look like percentages (0-100)
        if values.between(0, 100).all() and '%' in col.lower():
            return True
            
        return False
    
    def set_column_types(self, column_types: Dict[str, List[str]]):
        """Override automatic column type detection."""
        self._column_mappings.update(column_types)
        return self
    
    def _format_currency(self, val):
        """Format currency values with proper negative display."""
        if pd.isna(val):
            return ''
        try:
            symbol = self.config.currency_symbol
            precision = self.config.currency_precision
            if val < 0:
                return f"({symbol}{abs(val):,.{precision}f})"
            return f"{symbol}{val:,.{precision}f}"
        except:
            return str(val)
    
    def _format_percentage(self, val):
        """Format percentage values intelligently."""
        if pd.isna(val):
            return ''
        try:
            precision = self.config.percentage_precision
            if 0 <= abs(val) <= 1:
                return f"{val * 100:.{precision}f}%"
            return f"{val:.{precision}f}%"
        except:
            return str(val)
    
    def _format_number(self, val):
        """Format numeric values with thousands separators."""
        if pd.isna(val):
            return ''
        try:
            precision = self.config.number_precision
            return f"{val:,.{precision}f}"
        except:
            return str(val)
    
    def _format_date(self, val):
        """Format date values consistently."""
        if pd.isna(val):
            return ''
        try:
            if isinstance(val, str):
                val = pd.to_datetime(val)
            return val.strftime(self.config.date_format)
        except:
            return str(val)
    
    def create_styled_table(self, title: str = None, 
                           highlight_negatives: bool = True,
                           max_rows: Optional[int] = None) -> pd.io.formats.style.Styler:
        """Create professionally styled DataFrame."""
        df = self.df.head(max_rows) if max_rows else self.df
        styler = df.style
        
        # Apply formatters
        formatters = {}
        for col_type, format_func in [
            ('currency', self._format_currency),
            ('percentage', self._format_percentage), 
            ('number', self._format_number),
            ('date', self._format_date)
        ]:
            for col in self._column_mappings.get(col_type, []):
                if col in df.columns:
                    formatters[col] = format_func
        
        if formatters:
            styler = styler.format(formatters)
        
        # Color negative values
        if highlight_negatives:
            def color_negatives(val):
                try:
                    if pd.isna(val) or not isinstance(val, (int, float)):
                        return ''
                    if val < 0:
                        return f'color: {self.config.negative_color}; font-weight: bold;'
                    elif val > 0:
                        return f'color: {self.config.positive_color};'
                    return f'color: {self.config.neutral_color};'
                except:
                    return ''
            
            numeric_cols = (self._column_mappings.get('currency', []) + 
                           self._column_mappings.get('number', []) + 
                           self._column_mappings.get('percentage', []))
            
            for col in numeric_cols:
                if col in df.columns:
                    styler = styler.applymap(color_negatives, subset=[col])
        
        # Apply professional table styles
        styler = styler.set_table_styles([
            {'selector': 'table', 'props': [
                ('border-collapse', 'collapse'), ('width', '100%'),
                ('font-family', self.config.font_family), ('font-size', self.config.font_size),
                ('margin', '15px 0'), ('box-shadow', '0 2px 8px rgba(0,0,0,0.1)')
            ]},
            {'selector': 'th', 'props': [
                ('background-color', self.config.header_bg_color), 
                ('color', self.config.header_text_color),
                ('font-weight', 'bold'), ('padding', '12px 15px'),
                ('text-align', 'left'), ('border', f'1px solid {self.config.border_color}')
            ]},
            {'selector': 'td', 'props': [
                ('padding', '10px 15px'), 
                ('border', f'1px solid {self.config.border_color}')
            ]},
            {'selector': 'tr:nth-child(even)', 'props': [
                ('background-color', self.config.alternate_row_color)
            ]},
            {'selector': 'tr:hover', 'props': [
                ('background-color', '#f0f0f0'), ('cursor', 'pointer')
            ]}
        ])
        
        if title:
            styler = styler.set_caption(title).set_table_styles([
                {'selector': 'caption', 'props': [
                    ('font-size', '16px'), ('font-weight', 'bold'),
                    ('margin-bottom', '10px'), ('text-align', 'center')
                ]}
            ], overwrite=False)
        
        return styler


class EmailComponent(ABC):
    """Base class for email report components."""
    
    def __init__(self, id: str = None, title: str = None, 
                 config: StyleConfig = None):
        self.id = id or f"comp-{str(uuid.uuid4())[:8]}"
        self.title = title
        self.config = config or StyleConfig()
        
    @abstractmethod
    def to_html(self) -> str:
        """Convert component to email-compatible HTML."""
        pass
        
    def _wrap_with_container(self, content: str) -> str:
        """Wrap content in email-safe container."""
        title_html = ""
        if self.title:
            title_html = f"""
            <tr>
                <td style="padding: 10px 15px; background-color: #f5f5f5; border-bottom: 1px solid #e0e0e0;">
                    <h2 style="margin: 0; color: #333; font-size: 18px; font-weight: bold;">{self.title}</h2>
                </td>
            </tr>
            """
        
        return f"""
        <table style="width: 100%; max-width: {self.config.email_max_width}; margin: {self.config.component_margin}; 
               border-collapse: collapse; border: 1px solid #e0e0e0; background-color: #ffffff;">
            {title_html}
            <tr>
                <td style="padding: {self.config.component_padding};">
                    {content}
                </td>
            </tr>
        </table>
        """


class TextComponent(EmailComponent):
    """Professional text component with markdown support."""
    
    def __init__(self, text: str, markdown_enabled: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.markdown_enabled = markdown_enabled
        
    def to_html(self) -> str:
        if self.markdown_enabled and HAS_MARKDOWN:
            html_content = markdown.markdown(self.text)
            html_content = self._apply_email_styles(html_content)
        else:
            html_content = self.text.replace('\n', '<br>')
        
        return self._wrap_with_container(html_content)
    
    def _apply_email_styles(self, html: str) -> str:
        """Apply email-safe styles to HTML content."""
        replacements = {
            '<h1>': '<h1 style="color: #333; font-size: 24px; margin: 15px 0;">',
            '<h2>': '<h2 style="color: #333; font-size: 20px; margin: 12px 0;">',
            '<h3>': '<h3 style="color: #333; font-size: 18px; margin: 10px 0;">',
            '<p>': '<p style="color: #666; line-height: 1.6; margin: 10px 0;">',
            '<ul>': '<ul style="color: #666; margin: 10px 0; padding-left: 25px;">',
            '<strong>': '<strong style="color: #333;">',
            '<em>': '<em style="color: #666;">',
        }
        
        for old, new in replacements.items():
            html = html.replace(old, new)
        return html


class StyledTableComponent(EmailComponent):
    """Enhanced table component using FinancialDataFrameStyler."""
    
    def __init__(self, df: pd.DataFrame, 
                 auto_style: bool = True,
                 column_types: Optional[Dict[str, List[str]]] = None,
                 highlight_negatives: bool = True,
                 max_rows: Optional[int] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.df = df
        self.auto_style = auto_style
        self.column_types = column_types
        self.highlight_negatives = highlight_negatives
        self.max_rows = max_rows
        
    def to_html(self) -> str:
        if self.auto_style:
            styler = FinancialDataFrameStyler(self.df, self.config)
            if self.column_types:
                styler.set_column_types(self.column_types)
            
            styled_table = styler.create_styled_table(
                title=None,  # We handle title in container
                highlight_negatives=self.highlight_negatives,
                max_rows=self.max_rows
            )
            
            table_html = styled_table.to_html()
        else:
            # Simple table formatting
            table_html = self._create_simple_table_html()
        
        # Make email compatible
        table_html = self._make_email_compatible(table_html)
        return self._wrap_with_container(table_html)
    
    def _create_simple_table_html(self) -> str:
        """Create simple HTML table without pandas styling."""
        df = self.df.head(self.max_rows) if self.max_rows else self.df
        
        html = '<table style="width: 100%; border-collapse: collapse; font-family: Arial, sans-serif;">\n'
        
        # Header
        html += '<thead><tr>\n'
        for col in df.columns:
            html += f'<th style="background-color: {self.config.header_bg_color}; color: white; padding: 10px; border: 1px solid #ddd;">{col}</th>\n'
        html += '</tr></thead>\n'
        
        # Body
        html += '<tbody>\n'
        for idx, row in df.iterrows():
            bg_color = self.config.alternate_row_color if idx % 2 == 0 else 'white'
            html += f'<tr style="background-color: {bg_color};">\n'
            for col in df.columns:
                value = row[col]
                html += f'<td style="padding: 8px 10px; border: 1px solid #ddd;">{value}</td>\n'
            html += '</tr>\n'
        html += '</tbody></table>\n'
        
        return html
    
    def _make_email_compatible(self, html: str) -> str:
        """Convert styled HTML to email-compatible format."""
        # Remove CSS classes and convert to inline styles
        replacements = {
            'class="dataframe"': '',
            '<table ': '<table style="width: 100%; border-collapse: collapse; font-family: Arial, sans-serif;" ',
        }
        
        for old, new in replacements.items():
            html = html.replace(old, new)
        
        return html


class PlotlyChartComponent(EmailComponent):
    """Enhanced plotly component with automatic chart generation."""
    
    def __init__(self, figure: Optional[go.Figure] = None,
                 df: Optional[pd.DataFrame] = None,
                 chart_type: str = 'auto',
                 x_col: Optional[str] = None,
                 y_col: Optional[str] = None,
                 color_col: Optional[str] = None,
                 width: int = 800, height: int = 500,
                 **kwargs):
        super().__init__(**kwargs)
        self.figure = figure
        self.df = df
        self.chart_type = chart_type
        self.x_col = x_col
        self.y_col = y_col
        self.color_col = color_col
        self.width = width
        self.height = height
        
        if not HAS_PLOTLY:
            raise ImportError("plotly is required for PlotlyChartComponent")
    
    def _create_auto_chart(self) -> go.Figure:
        """Automatically create appropriate chart based on data types."""
        if self.df is None:
            raise ValueError("DataFrame required for auto chart generation")
        
        # Detect column types
        styler = FinancialDataFrameStyler(self.df)
        mappings = styler._column_mappings
        
        numeric_cols = mappings.get('currency', []) + mappings.get('number', [])
        date_cols = mappings.get('date', [])
        text_cols = mappings.get('text', [])
        
        # Auto-select columns if not specified
        if not self.x_col and not self.y_col:
            if date_cols and numeric_cols:
                # Time series chart
                self.x_col = date_cols[0]
                self.y_col = numeric_cols[0]
                chart_type = 'line'
            elif text_cols and numeric_cols:
                # Bar chart
                self.x_col = text_cols[0]
                self.y_col = numeric_cols[0]
                chart_type = 'bar'
            else:
                # Default to scatter
                chart_type = 'scatter'
                if len(numeric_cols) >= 2:
                    self.x_col = numeric_cols[0]
                    self.y_col = numeric_cols[1]
        
        # Create chart based on detected or specified type
        if self.chart_type == 'auto':
            self.chart_type = chart_type
        
        if self.chart_type == 'line':
            fig = px.line(self.df, x=self.x_col, y=self.y_col, 
                         color=self.color_col, title=self.title)
        elif self.chart_type == 'bar':
            fig = px.bar(self.df, x=self.x_col, y=self.y_col,
                        color=self.color_col, title=self.title)
        elif self.chart_type == 'scatter':
            fig = px.scatter(self.df, x=self.x_col, y=self.y_col,
                           color=self.color_col, title=self.title)
        elif self.chart_type == 'pie':
            fig = px.pie(self.df, values=self.y_col, names=self.x_col, title=self.title)
        else:
            # Default line chart
            fig = px.line(self.df, x=self.x_col, y=self.y_col, title=self.title)
        
        # Apply professional styling
        fig.update_layout(
            template="plotly_white",
            font=dict(family="Arial, sans-serif", size=12),
            title_font_size=16,
            showlegend=bool(self.color_col),
            margin=dict(l=50, r=50, t=60, b=50)
        )
        
        return fig
    
    def to_html(self) -> str:
        if self.figure is None:
            self.figure = self._create_auto_chart()
        
        # Convert to static image
        try:
            img_bytes = self.figure.to_image(
                format="png", width=self.width, height=self.height, scale=2.0
            )
            img_base64 = base64.b64encode(img_bytes).decode()
            
            img_html = f'''
            <div style="text-align: center;">
                <img src="data:image/png;base64,{img_base64}" 
                     alt="Chart" 
                     style="max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 5px;">
            </div>
            '''
            
            return self._wrap_with_container(img_html)
            
        except Exception as e:
            error_html = f'<p style="color: red;">Error generating chart: {str(e)}</p>'
            return self._wrap_with_container(error_html)


class EmailReport:
    """Professional email report orchestrator."""
    
    def __init__(self, title: str, config: EmailConfig, 
                 style_config: StyleConfig = None):
        self.title = title
        self.config = config
        self.style_config = style_config or StyleConfig()
        self.components: List[EmailComponent] = []
        
    def add_text(self, text: str, **kwargs) -> TextComponent:
        """Add professional text component."""
        component = TextComponent(text, config=self.style_config, **kwargs)
        self.components.append(component)
        return component
    
    def add_dataframe(self, df: pd.DataFrame, **kwargs) -> StyledTableComponent:
        """Add intelligently styled DataFrame."""
        component = StyledTableComponent(df, config=self.style_config, **kwargs)
        self.components.append(component)
        return component
    
    def add_chart(self, figure: go.Figure = None, df: pd.DataFrame = None, 
                  **kwargs) -> PlotlyChartComponent:
        """Add plotly chart with auto-generation capabilities."""
        component = PlotlyChartComponent(
            figure=figure, df=df, config=self.style_config, **kwargs
        )
        self.components.append(component)
        return component
    
    def generate_html(self) -> str:
        """Generate professional email-ready HTML."""
        components_html = '\n'.join([comp.to_html() for comp in self.components])
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title}</title>
    <style>
        body {{ 
            font-family: {self.style_config.font_family}; 
            line-height: 1.6; margin: 0; padding: 20px; 
            background-color: #f8f9fa; 
        }}
        .email-container {{ 
            max-width: {self.style_config.email_max_width}; 
            margin: 0 auto; background-color: #ffffff; 
            border-radius: 8px; overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1); 
        }}
        .header {{ 
            background: linear-gradient(135deg, {self.style_config.header_bg_color} 0%, #34495e 100%);
            color: white; padding: 30px; text-align: center; 
        }}
        .content {{ padding: 20px; }}
        .footer {{ 
            background-color: #f8f9fa; padding: 20px; text-align: center;
            font-size: 11px; color: #666; border-top: 1px solid #e0e0e0;
        }}
        h1 {{ margin: 0; font-size: 28px; font-weight: 300; }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>{self.title}</h1>
        </div>
        <div class="content">
            {components_html}
        </div>
        <div class="footer">
            <p>Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')} | Professional Quantitative Report</p>
        </div>
    </div>
</body>
</html>'''
    
    def save(self, filename: str = None) -> str:
        """Save report to HTML file."""
        filename = filename or f"report_{self.title.lower().replace(' ', '_')}.html"
        html = self.generate_html()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"Professional email report saved: {filename}")
        return filename


# Professional utility functions
def create_sample_portfolio_data():
    """Generate realistic portfolio data for testing."""
    np.random.seed(42)
    
    strategies = ['Equity Long/Short', 'Fixed Income Arb', 'Volatility Trading', 
                  'Market Neutral', 'Event Driven', 'Macro Trading']
    
    return pd.DataFrame({
        'Strategy': strategies,
        'Daily_PnL_USD': np.random.normal(150000, 300000, len(strategies)),
        'MTD_PnL_USD': np.random.normal(2500000, 1200000, len(strategies)),
        'YTD_Return_Pct': np.random.normal(12.5, 8.0, len(strategies)),
        'Sharpe_Ratio': np.random.uniform(0.8, 2.2, len(strategies)),
        'Max_Drawdown_Pct': -np.abs(np.random.normal(4.5, 2.5, len(strategies))),
        'AUM_USD': np.random.uniform(50e6, 500e6, len(strategies)),
        'Last_Updated': pd.Timestamp.now()
    })


def demo_professional_report():
    """Demonstrate the professional email report system."""
    # Configuration
    email_config = EmailConfig(
        sender="quant@hedgefund.com",
        recipients=["pm@hedgefund.com", "risk@hedgefund.com"],
        subject="Daily Portfolio Performance & Risk Report"
    )
    
    style_config = StyleConfig(
        currency_symbol='$',
        header_bg_color='#2c3e50',
        negative_color='#e74c3c',
        positive_color='#27ae60'
    )
    
    # Create report
    report = EmailReport("Daily Quantitative Analysis", email_config, style_config)
    
    # Executive summary
    report.add_text("""
## Executive Summary

**Strong Performance Today**: Portfolio delivered **+1.94%** return

### Key Highlights:
* **Top Performer**: Equity Long/Short strategy (+2.8%)
* **Risk Metrics**: All within target limits
* **Volatility**: Decreased 15% from yesterday
* **Sharpe Ratio**: Improved to 1.67 YTD

**Market Outlook**: Continued momentum expected with controlled risk exposure.
    """, title="Daily Performance Summary")
    
    # Portfolio data
    portfolio_df = create_sample_portfolio_data()
    
    # Add styled table
    report.add_dataframe(
        portfolio_df, 
        title="Strategy Performance Breakdown",
        highlight_negatives=True,
        max_rows=10
    )
    
    # Add auto-generated chart
    if HAS_PLOTLY:
        report.add_chart(
            df=portfolio_df,
            chart_type='bar',
            x_col='Strategy', 
            y_col='YTD_Return_Pct',
            title="YTD Returns by Strategy"
        )
    
    # Save report
    filename = report.save()
    return filename


if __name__ == "__main__":
    print("Professional Email Report Library")
    print("=" * 50)
    
    demo_file = demo_professional_report()
    print(f"\nDemo report generated: {demo_file}")
    
    print("\nFeatures included:")
    print("✓ Intelligent DataFrame styling with auto-detection")
    print("✓ Professional email-compatible HTML")
    print("✓ Automatic chart generation from data")
    print("✓ Financial number formatting")
    print("✓ Responsive design for all email clients")
