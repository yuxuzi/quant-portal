"""
Excel Report Library - Structured library for creating Excel reports with native formatting,
DataFrames, and embedded plotly charts.
Optimized for quantitative finance teams using openpyxl and plotly/kaleido stack.
"""

import uuid
import io
import os
from typing import List, Dict, Any, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import numpy as np

try:
    import openpyxl
    from openpyxl import Workbook
    from openpyxl.styles import Font, Fill, Border, Side, Alignment, NamedStyle, PatternFill
    from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, IconSetRule, CellIsRule
    from openpyxl.chart import LineChart, BarChart, ScatterChart, PieChart
    from openpyxl.drawing.image import Image
    from openpyxl.utils.dataframe import dataframe_to_rows
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    import plotly.io as pio
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


@dataclass
class ExcelStyle:
    """Excel cell styling configuration."""
    font_name: str = "Calibri"
    font_size: int = 11
    font_bold: bool = False
    font_color: str = "000000"  # Black
    fill_color: Optional[str] = None  # Hex color without #
    border_style: str = "thin"  # thin, medium, thick
    border_color: str = "000000"
    alignment_horizontal: str = "general"  # left, center, right, general
    alignment_vertical: str = "bottom"  # top, center, bottom
    number_format: str = "General"


@dataclass
class TableStyle:
    """Predefined table styling configurations."""
    header: ExcelStyle = field(default_factory=lambda: ExcelStyle(
        font_bold=True, fill_color="D9E1F2", alignment_horizontal="center"
    ))
    data: ExcelStyle = field(default_factory=lambda: ExcelStyle())
    alternating_row: ExcelStyle = field(default_factory=lambda: ExcelStyle(fill_color="F2F2F2"))
    
    @classmethod
    def financial_table(cls):
        """Financial/trading table style."""
        return cls(
            header=ExcelStyle(font_bold=True, fill_color="4472C4", font_color="FFFFFF", 
                            alignment_horizontal="center"),
            data=ExcelStyle(alignment_horizontal="right"),
            alternating_row=ExcelStyle(fill_color="F8F9FA")
        )
    
    @classmethod
    def risk_table(cls):
        """Risk metrics table style."""
        return cls(
            header=ExcelStyle(font_bold=True, fill_color="E74C3C", font_color="FFFFFF",
                            alignment_horizontal="center"),
            data=ExcelStyle(alignment_horizontal="center"),
            alternating_row=ExcelStyle(fill_color="FADBD8")
        )
    
    @classmethod
    def pnl_table(cls):
        """P&L table style with green/red formatting."""
        return cls(
            header=ExcelStyle(font_bold=True, fill_color="28A745", font_color="FFFFFF",
                            alignment_horizontal="center"),
            data=ExcelStyle(alignment_horizontal="right"),
            alternating_row=ExcelStyle(fill_color="E8F5E8")
        )


class ExcelComponent:
    """Base class for Excel report components."""
    
    def __init__(self, title: str = None, start_row: int = 1, start_col: int = 1):
        """
        Initialize Excel component.
        
        Args:
            title: Component title
            start_row: Starting row (1-based)
            start_col: Starting column (1-based)
        """
        self.title = title
        self.start_row = start_row
        self.start_col = start_col
        self.end_row = start_row
        self.end_col = start_col
        
    def write_to_worksheet(self, worksheet, current_row: int = None) -> int:
        """Write component to worksheet and return next available row."""
        raise NotImplementedError("Subclasses must implement write_to_worksheet")
        
    def _apply_style(self, cell, style: ExcelStyle):
        """Apply ExcelStyle to a cell."""
        if not HAS_OPENPYXL:
            return
            
        # Font styling
        cell.font = Font(
            name=style.font_name,
            size=style.font_size,
            bold=style.font_bold,
            color=style.font_color
        )
        
        # Fill styling
        if style.fill_color:
            cell.fill = PatternFill(start_color=style.fill_color, end_color=style.fill_color, fill_type="solid")
            
        # Border styling
        border_side = Side(style=style.border_style, color=style.border_color)
        cell.border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
        
        # Alignment
        cell.alignment = Alignment(
            horizontal=style.alignment_horizontal,
            vertical=style.alignment_vertical
        )
        
        # Number format
        cell.number_format = style.number_format


class TextComponent(ExcelComponent):
    """Component for text content in Excel."""
    
    def __init__(self, text: str, style: ExcelStyle = None, **kwargs):
        """
        Initialize text component.
        
        Args:
            text: Text content
            style: Excel styling
            **kwargs: Additional component arguments
        """
        super().__init__(**kwargs)
        self.text = text
        self.style = style or ExcelStyle(font_size=12)
        
    def write_to_worksheet(self, worksheet, current_row: int = None) -> int:
        """Write text to worksheet."""
        row = current_row or self.start_row
        
        # Add title if provided
        if self.title:
            title_cell = worksheet.cell(row=row, column=self.start_col, value=self.title)
            title_style = ExcelStyle(font_bold=True, font_size=14)
            self._apply_style(title_cell, title_style)
            row += 2
            
        # Add text content
        text_cell = worksheet.cell(row=row, column=self.start_col, value=self.text)
        self._apply_style(text_cell, self.style)
        
        self.end_row = row
        return row + 2  # Return next available row with spacing


class DataFrameComponent(ExcelComponent):
    """Component for DataFrames with native Excel formatting."""
    
    def __init__(self, df: pd.DataFrame, 
                 table_style: TableStyle = None,
                 number_formats: Optional[Dict[str, str]] = None,
                 conditional_formatting: Optional[Dict[str, Any]] = None,
                 freeze_header: bool = True,
                 autofit_columns: bool = True,
                 **kwargs):
        """
        Initialize DataFrame component.
        
        Args:
            df: pandas DataFrame
            table_style: TableStyle configuration
            number_formats: Column-specific number formatting {'col': 'format'}
            conditional_formatting: Conditional formatting rules
            freeze_header: Whether to freeze header row
            autofit_columns: Whether to auto-fit column widths
            **kwargs: Additional component arguments
        """
        super().__init__(**kwargs)
        self.df = df
        self.table_style = table_style or TableStyle()
        self.number_formats = number_formats or {}
        self.conditional_formatting = conditional_formatting or {}
        self.freeze_header = freeze_header
        self.autofit_columns = autofit_columns
        
    def write_to_worksheet(self, worksheet, current_row: int = None) -> int:
        """Write DataFrame to worksheet with native Excel formatting."""
        start_row = current_row or self.start_row
        
        # Add title if provided
        if self.title:
            title_cell = worksheet.cell(row=start_row, column=self.start_col, value=self.title)
            title_style = ExcelStyle(font_bold=True, font_size=14)
            self._apply_style(title_cell, title_style)
            start_row += 2
            
        # Write DataFrame to worksheet
        df_start_row = start_row
        
        # Write headers
        for col_idx, column in enumerate(self.df.columns):
            cell = worksheet.cell(row=df_start_row, column=self.start_col + col_idx, value=column)
            self._apply_style(cell, self.table_style.header)
            
        # Write data rows
        for row_idx, row_data in enumerate(self.df.itertuples(index=False)):
            excel_row = df_start_row + 1 + row_idx
            
            # Determine if alternating row
            use_alt_style = row_idx % 2 == 1 and self.table_style.alternating_row.fill_color
            row_style = self.table_style.alternating_row if use_alt_style else self.table_style.data
            
            for col_idx, value in enumerate(row_data):
                cell = worksheet.cell(row=excel_row, column=self.start_col + col_idx, value=value)
                
                # Apply base style
                self._apply_style(cell, row_style)
                
                # Apply column-specific number formatting
                col_name = self.df.columns[col_idx]
                if col_name in self.number_formats:
                    cell.number_format = self.number_formats[col_name]
                    
        # Apply conditional formatting
        self._apply_conditional_formatting(worksheet, df_start_row)
        
        # Auto-fit columns
        if self.autofit_columns:
            self._autofit_columns(worksheet)
            
        # Freeze header
        if self.freeze_header:
            worksheet.freeze_panes = worksheet.cell(row=df_start_row + 1, column=1)
            
        self.end_row = df_start_row + len(self.df)
        return self.end_row + 3  # Return next available row with spacing
        
    def _apply_conditional_formatting(self, worksheet, header_row: int):
        """Apply conditional formatting rules."""
        if not self.conditional_formatting:
            return
            
        data_start_row = header_row + 1
        data_end_row = header_row + len(self.df)
        
        for col_name, formatting_rule in self.conditional_formatting.items():
            if col_name not in self.df.columns:
                continue
                
            col_idx = list(self.df.columns).index(col_name)
            col_letter = get_column_letter(self.start_col + col_idx)
            cell_range = f"{col_letter}{data_start_row}:{col_letter}{data_end_row}"
            
            rule_type = formatting_rule.get('type')
            
            if rule_type == 'color_scale':
                # Color scale formatting (red-yellow-green)
                rule = ColorScaleRule(
                    start_type='min', start_color='FF6B6B',  # Red
                    mid_type='percentile', mid_value=50, mid_color='FFE66D',  # Yellow
                    end_type='max', end_color='4ECDC4'  # Green
                )
                worksheet.conditional_formatting.add(cell_range, rule)
                
            elif rule_type == 'data_bars':
                # Data bars
                rule = DataBarRule(
                    start_type='min', end_type='max',
                    color='4472C4', showValue=True
                )
                worksheet.conditional_formatting.add(cell_range, rule)
                
            elif rule_type == 'positive_negative':
                # Color positive values green, negative red
                pos_rule = CellIsRule(operator='greaterThan', formula=['0'], 
                                    fill=PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid'),
                                    font=Font(color='006100'))
                neg_rule = CellIsRule(operator='lessThan', formula=['0'],
                                    fill=PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid'),
                                    font=Font(color='9C0006'))
                worksheet.conditional_formatting.add(cell_range, pos_rule)
                worksheet.conditional_formatting.add(cell_range, neg_rule)
                
    def _autofit_columns(self, worksheet):
        """Auto-fit column widths based on content."""
        for col_idx, column in enumerate(self.df.columns):
            column_letter = get_column_letter(self.start_col + col_idx)
            
            # Calculate max width needed
            max_length = len(str(column))  # Header length
            for value in self.df.iloc[:, col_idx]:
                max_length = max(max_length, len(str(value)))
                
            # Set column width (with some padding)
            worksheet.column_dimensions[column_letter].width = min(max_length + 2, 50)


class PlotlyChartComponent(ExcelComponent):
    """Component for embedding plotly charts as images in Excel."""
    
    def __init__(self, figure: Optional[go.Figure] = None,
                 plot_function: Optional[Callable] = None,
                 plot_args: tuple = (),
                 plot_kwargs: dict = None,
                 image_format: str = "png",
                 width: int = 800,
                 height: int = 500,
                 scale: float = 2.0,
                 **kwargs):
        """
        Initialize plotly chart component.
        
        Args:
            figure: plotly Figure object
            plot_function: Function that returns a plotly figure
            plot_args: Arguments for plot_function
            plot_kwargs: Keyword arguments for plot_function
            image_format: Image format ('png', 'jpg')
            width: Image width in pixels
            height: Image height in pixels
            scale: Scale factor for high-DPI displays
            **kwargs: Additional component arguments
        """
        super().__init__(**kwargs)
        self.figure = figure
        self.plot_function = plot_function
        self.plot_args = plot_args
        self.plot_kwargs = plot_kwargs or {}
        self.image_format = image_format
        self.width = width
        self.height = height
        self.scale = scale
        
        if not HAS_PLOTLY:
            raise ImportError("plotly is required for PlotlyChartComponent")
            
    def write_to_worksheet(self, worksheet, current_row: int = None) -> int:
        """Write plotly chart as image to worksheet."""
        start_row = current_row or self.start_row
        
        # Add title if provided
        if self.title:
            title_cell = worksheet.cell(row=start_row, column=self.start_col, value=self.title)
            title_style = ExcelStyle(font_bold=True, font_size=14)
            self._apply_style(title_cell, title_style)
            start_row += 2
            
        # Generate figure if needed
        if self.figure is None:
            if self.plot_function:
                self.figure = self.plot_function(*self.plot_args, **self.plot_kwargs)
            else:
                # Create placeholder text
                placeholder_cell = worksheet.cell(row=start_row, column=self.start_col, 
                                                value="No chart data available")
                return start_row + 2
                
        # Convert plotly figure to image bytes
        img_bytes = self.figure.to_image(
            format=self.image_format,
            width=self.width,
            height=self.height,
            scale=self.scale
        )
        
        # Create temporary file for image
        temp_filename = f"temp_chart_{uuid.uuid4().hex[:8]}.{self.image_format}"
        try:
            with open(temp_filename, 'wb') as f:
                f.write(img_bytes)
                
            # Insert image into worksheet
            img = Image(temp_filename)
            
            # Position image
            cell_address = worksheet.cell(row=start_row, column=self.start_col).coordinate
            img.anchor = cell_address
            
            # Scale image to fit nicely in Excel
            img.width = self.width * 0.75  # Scale down for Excel
            img.height = self.height * 0.75
            
            worksheet.add_image(img)
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
        # Calculate rows occupied by image (rough estimate)
        rows_occupied = max(int(self.height * 0.75 / 20), 15)  # ~20 pixels per row
        self.end_row = start_row + rows_occupied
        
        return self.end_row + 2  # Return next available row


class ExcelReport:
    """Main Excel report class that combines components across multiple worksheets."""
    
    def __init__(self, filename: str, title: str = None):
        """
        Initialize Excel report.
        
        Args:
            filename: Output Excel filename
            title: Report title
        """
        self.filename = filename
        self.title = title or "Quantitative Report"
        self.workbook = Workbook() if HAS_OPENPYXL else None
        self.worksheets: Dict[str, Any] = {}
        self.components: Dict[str, List[ExcelComponent]] = {}
        
        if not HAS_OPENPYXL:
            raise ImportError("openpyxl is required for ExcelReport")
            
        # Remove default worksheet and create summary
        self.workbook.remove(self.workbook.active)
        self._create_summary_worksheet()
        
    def _create_summary_worksheet(self):
        """Create summary/cover worksheet."""
        summary_ws = self.workbook.create_sheet("Summary", 0)
        self.worksheets["Summary"] = summary_ws
        self.components["Summary"] = []
        
        # Add report title and metadata
        title_component = TextComponent(
            text=self.title,
            style=ExcelStyle(font_size=20, font_bold=True),
            start_row=2
        )
        
        metadata_text = f"""Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
This report contains quantitative analysis including:
• Performance metrics and P&L breakdown
• Risk analysis and exposure metrics  
• Market data and statistical summaries
• Interactive charts and visualizations"""
        
        metadata_component = TextComponent(
            text=metadata_text,
            style=ExcelStyle(font_size=11),
            start_row=5
        )
        
        self.components["Summary"] = [title_component, metadata_component]
        
    def create_worksheet(self, name: str) -> Any:
        """Create a new worksheet."""
        if name in self.worksheets:
            return self.worksheets[name]
            
        worksheet = self.workbook.create_sheet(name)
        self.worksheets[name] = worksheet
        self.components[name] = []
        return worksheet
        
    def add_component(self, component: ExcelComponent, worksheet_name: str = "Summary"):
        """Add component to specific worksheet."""
        if worksheet_name not in self.worksheets:
            self.create_worksheet(worksheet_name)
            
        self.components[worksheet_name].append(component)
        
    def add_text(self, text: str, worksheet_name: str = "Summary", **kwargs) -> TextComponent:
        """Add text component to worksheet."""
        component = TextComponent(text, **kwargs)
        self.add_component(component, worksheet_name)
        return component
        
    def add_dataframe(self, df: pd.DataFrame, worksheet_name: str = "Data", **kwargs) -> DataFrameComponent:
        """Add DataFrame component to worksheet."""
        component = DataFrameComponent(df, **kwargs)
        self.add_component(component, worksheet_name)
        return component
        
    def add_plotly_chart(self, figure: go.Figure = None, worksheet_name: str = "Charts", **kwargs) -> PlotlyChartComponent:
        """Add plotly chart component to worksheet."""
        component = PlotlyChartComponent(figure=figure, **kwargs)
        self.add_component(component, worksheet_name)
        return component
        
    def generate_report(self) -> str:
        """Generate the complete Excel report."""
        # Write all components to their respective worksheets
        for ws_name, components in self.components.items():
            worksheet = self.worksheets[ws_name]
            current_row = 1
            
            for component in components:
                current_row = component.write_to_worksheet(worksheet, current_row)
                
        # Save workbook
        self.workbook.save(self.filename)
        return self.filename
        
    def save(self) -> str:
        """Save the Excel report."""
        return self.generate_report()


# Helper functions for common quant formatting
def get_financial_number_formats():
    """Get common financial number formats."""
    return {
        'currency': '"$"#,##0.00',
        'currency_millions': '"$"#,##0,,"M"',
        'percentage': '0.00%',
        'basis_points': '0"bp"',
        'ratio': '0.00',
        'large_number': '#,##0',
        'return_pct': '0.00"%"',
        'pnl': '"$"#,##0.00_);[Red]("$"#,##0.00)',
    }


def create_pnl_conditional_formatting():
    """Get P&L specific conditional formatting rules."""
    return {
        'type': 'positive_negative'
    }


def create_sample_quant_excel_report():
    """Create a comprehensive sample Excel report for quant teams."""
    
    # Create report
    report = ExcelReport("daily_quant_report.xlsx", "Daily Quantitative Analysis Report")
    
    # Add summary text
    report.add_text("""
Daily Performance Summary:
• Portfolio returned +1.87% today
• Outperformed benchmark by +0.92%
• All risk limits maintained within targets
• Strong performance in equity long/short strategy
    """, worksheet_name="Summary", title="Executive Summary")
    
    # Create sample P&L data
    np.random.seed(42)
    strategies = ['Equity Long/Short', 'Fixed Income Arb', 'Volatility Trading', 
                  'Market Neutral', 'Event Driven']
    
    pnl_data = pd.DataFrame({
        'Strategy': strategies,
        'Daily_PnL_MM': np.random.normal(1.5, 2.0, 5),
        'MTD_PnL_MM': np.random.normal(8.0, 12.0, 5),
        'YTD_PnL_MM': np.random.normal(45.0, 35.0, 5),
        'Daily_Return_Pct': np.random.normal(1.2, 1.8, 5),
        'Sharpe_Ratio': np.random.uniform(0.8, 2.5, 5),
        'Max_DD_Pct': -np.abs(np.random.normal(3.0, 2.0, 5)),
        'AUM_MM': np.random.uniform(50, 200, 5)
    })
    
    # Add P&L table with financial formatting
    financial_formats = get_financial_number_formats()
    pnl_formats = {
        'Daily_PnL_MM': financial_formats['pnl'],
        'MTD_PnL_MM': financial_formats['currency_millions'], 
        'YTD_PnL_MM': financial_formats['currency_millions'],
        'Daily_Return_Pct': financial_formats['percentage'],
        'Sharpe_Ratio': financial_formats['ratio'],
        'Max_DD_Pct': financial_formats['percentage'],
        'AUM_MM': financial_formats['currency_millions']
    }
    
    pnl_conditional = {
        'Daily_PnL_MM': create_pnl_conditional_formatting(),
        'Daily_Return_Pct': {'type': 'color_scale'},
        'Sharpe_Ratio': {'type': 'data_bars'}
    }
    
    report.add_dataframe(
        pnl_data,
        worksheet_name="P&L Analysis", 
        title="Strategy Performance Breakdown",
        table_style=TableStyle.pnl_table(),
        number_formats=pnl_formats,
        conditional_formatting=pnl_conditional
    )
    
    # Create risk metrics table
    risk_data = pd.DataFrame({
        'Risk_Metric': ['VaR (99%, 1-day)', 'Expected Shortfall', 'Portfolio Beta', 
                       'Correlation to SPY', 'Max Drawdown', 'Volatility (Ann.)'],
        'Current_Value': [2.34, 3.12, 0.67, 0.74, -2.1, 14.2],
        'Limit_Target': [5.0, 4.0, 1.0, 0.8, -5.0, 18.0],
        'Utilization_Pct': [46.8, 78.0, 67.0, 92.5, 42.0, 78.9],
        'Status': ['OK', 'OK', 'OK', 'WATCH', 'OK', 'OK']
    })
    
    risk_formats = {
        'Current_Value': financial_formats['ratio'],
        'Limit_Target': financial_formats['ratio'],
        'Utilization_Pct': financial_formats['percentage']
    }
    
    risk_conditional = {
        'Utilization_Pct': {'type': 'color_scale'},
    }
    
    report.add_dataframe(
        risk_data,
        worksheet_name="Risk Metrics",
        title="Daily Risk Dashboard", 
        table_style=TableStyle.risk_table(),
        number_formats=risk_formats,
        conditional_formatting=risk_conditional
    )
    
    # Add plotly charts if available
    if HAS_PLOTLY:
        # Cumulative returns chart
        dates = pd.date_range('2024-01-01', '2024-08-09', freq='D')
        portfolio_returns = np.random.normal(0.0008, 0.015, len(dates))
        benchmark_returns = np.random.normal(0.0005, 0.012, len(dates))
        
        portfolio_cum = (1 + pd.Series(portfolio_returns, index=dates)).cumprod()
        benchmark_cum = (1 + pd.Series(benchmark_returns, index=dates)).cumprod()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=(portfolio_cum-1)*100, name='Portfolio', 
                                line=dict(color='blue', width=2)))
        fig.add_trace(go.Scatter(x=dates, y=(benchmark_cum-1)*100, name='Benchmark', 
                                line=dict(color='gray', width=1, dash='dash')))
        
        fig.update_layout(
            title="Cumulative Returns Comparison",
            xaxis_title="Date",
            yaxis_title="Cumulative Return (%)",
            template="plotly_white"
        )
        
        report.add_plotly_chart(fig, worksheet_name="Charts", title="Performance Chart")
        
        # Risk decomposition pie chart
        risk_contrib = pd.DataFrame({
            'Strategy': strategies[:4],  # Top 4 for pie chart
            'Risk_Contribution': [35.2, 28.1, 22.7, 14.0]
        })
        
        fig2 = px.pie(risk_contrib, values='Risk_Contribution', names='Strategy', 
                     title='Risk Contribution by Strategy')
        fig2.update_traces(textposition='inside', textinfo='percent+label')
        
        report.add_plotly_chart(fig2, worksheet_name="Charts", title="Risk Decomposition")
    
    return report


if __name__ == "__main__":
    # Create and generate sample Excel report
    sample_report = create_sample_quant_excel_report()
    filename = sample_report.save()
    print(f"Excel report generated: {filename}")
