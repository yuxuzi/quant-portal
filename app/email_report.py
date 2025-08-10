"""
Professional Email Report Library
---------------------------------
- Intelligent DataFrame styling
- Email-ready HTML report generation
- Plotly chart embedding
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseSettings, Field

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


__all__ = [
    "EmailConfig",
    "StyleConfig",
    "FinancialDataFrameStyler",
    "EmailComponent",
    "TextComponent",
    "StyledTableComponent",
    "PlotlyChartComponent",
    "EmailReport",
    "create_sample_portfolio_data",
    "demo_professional_report",
]


# =======================================
# CONFIGURATION (Pydantic)
# =======================================

class EmailConfig(BaseSettings):
    """Email metadata configuration."""
    sender: str = Field(..., description="Sender email address")
    recipients: list[str] = Field(..., description="List of recipient emails")
    subject: str
    cc: list[str] | None = None
    bcc: list[str] | None = None
    reply_to: str | None = None

    class Config:
        env_prefix = "EMAIL_"
        env_file = ".env"


class StyleConfig(BaseSettings):
    """Styling configuration for reports."""
    currency_symbol: str = "$"
    currency_precision: int = 2
    percentage_precision: int = 2
    number_precision: int = 2
    date_format: str = "%Y-%m-%d"

    # Colors
    negative_color: str = "#FF6B6B"
    positive_color: str = "#51CF66"
    neutral_color: str = "#868E96"
    header_bg_color: str = "#2c3e50"
    header_text_color: str = "white"
    alternate_row_color: str = "#F8F9FA"
    border_color: str = "#DEE2E6"
    section_bg_color: str = "#f5f5f5"

    # Typography
    font_family: str = "Arial, sans-serif"
    font_size: str = "12px"

    # Layout
    email_max_width: str = "800px"
    component_margin: str = "20px 0"
    component_padding: str = "15px"

    class Config:
        env_prefix = "STYLE_"
        env_file = ".env"


# =======================================
# DATAFRAME STYLER
# =======================================

class FinancialDataFrameStyler:
    """Applies financial styling to Pandas DataFrames."""

    def __init__(self, df: pd.DataFrame, config: StyleConfig):
        self.df = df.copy()
        self.config = config
        self._column_types: dict[str, str] | None = None

    def _detect_column_types(self) -> dict[str, str]:
        """Detect semantic column types."""
        if self._column_types is None:
            self._column_types = {}
            for col in self.df.columns:
                if pd.api.types.is_numeric_dtype(self.df[col]):
                    if "pct" in col.lower() or "%" in col:
                        self._column_types[col] = "percentage"
                    elif "price" in col.lower() or "value" in col.lower():
                        self._column_types[col] = "currency"
                    else:
                        self._column_types[col] = "number"
                elif pd.api.types.is_datetime64_any_dtype(self.df[col]):
                    self._column_types[col] = "date"
                else:
                    self._column_types[col] = "text"
        return self._column_types

    def _apply_formatting(self, styler: pd.io.formats.style.Styler) -> pd.io.formats.style.Styler:
        """Apply formatting rules."""
        for col, col_type in self._detect_column_types().items():
            if col_type == "currency":
                styler = styler.format({col: f"{self.config.currency_symbol}{{:,.{self.config.currency_precision}f}}"})
            elif col_type == "percentage":
                styler = styler.format({col: f"{{:.{self.config.percentage_precision}%}}"})
            elif col_type == "number":
                styler = styler.format({col: f"{{:,.{self.config.number_precision}f}}"})
            elif col_type == "date":
                styler = styler.format({col: lambda x: x.strftime(self.config.date_format) if pd.notnull(x) else ""})
        return styler

    def _apply_color_coding(self, styler: pd.io.formats.style.Styler) -> pd.io.formats.style.Styler:
        """Apply conditional coloring for numeric values."""
        def color_negative_red(val: Any) -> str:
            if isinstance(val, (int, float, np.number)):
                if val < 0:
                    return f"color: {self.config.negative_color}"
                elif val > 0:
                    return f"color: {self.config.positive_color}"
            return f"color: {self.config.neutral_color}"
        return styler.applymap(color_negative_red)

    def to_html(self) -> str:
        """Render the styled DataFrame to HTML."""
        styler = self.df.style
        styler = self._apply_formatting(styler)
        styler = self._apply_color_coding(styler)
        styler.set_table_styles(
            [
                {"selector": "th", "props": [("background-color", self.config.header_bg_color),
                                              ("color", self.config.header_text_color),
                                              ("font-family", self.config.font_family),
                                              ("font-size", self.config.font_size)]},
                {"selector": "td", "props": [("font-family", self.config.font_family),
                                              ("font-size", self.config.font_size)]}
            ]
        )
        return styler.to_html()


# =======================================
# EMAIL COMPONENTS
# =======================================

class EmailComponent(ABC):
    """Base class for all email report components."""
    def __init__(self, config: StyleConfig):
        self.config = config

    @abstractmethod
    def render(self) -> str:
        """Render component HTML."""
        ...


class TextComponent(EmailComponent):
    """Text block component (Markdown supported)."""
    def __init__(self, content: str, config: StyleConfig):
        super().__init__(config)
        self.content = content

    def render(self) -> str:
        html = markdown.markdown(self.content) if HAS_MARKDOWN else f"<p>{self.content}</p>"
        return f'<div style="margin:{self.config.component_margin}; padding:{self.config.component_padding};">{html}</div>'


class StyledTableComponent(EmailComponent):
    """Styled Pandas DataFrame as HTML table."""
    def __init__(self, df: pd.DataFrame, config: StyleConfig):
        super().__init__(config)
        self.styler = FinancialDataFrameStyler(df, config)

    def render(self) -> str:
        return self.styler.to_html()


class PlotlyChartComponent(EmailComponent):
    """Plotly chart embedded as HTML <img> tag."""
    def __init__(self, fig: go.Figure, config: StyleConfig):
        if not HAS_PLOTLY:
            raise ImportError("Plotly is required for PlotlyChartComponent")
        super().__init__(config)
        self.fig = fig

    def render(self) -> str:
        img_bytes = self.fig.to_image(format="png")
        img_base64 = base64.b64encode(img_bytes).decode()
        return f'<div style="text-align:center;"><img src="data:image/png;base64,{img_base64}" style="max-width:100%;"></div>'


# =======================================
# REPORT BUILDER
# =======================================

class EmailReport:
    """Container for assembling email reports."""
    def __init__(self, email_config: EmailConfig, style_config: StyleConfig):
        self.email_config = email_config
        self.style_config = style_config
        self.components: list[EmailComponent] = []

    def add_component(self, component: EmailComponent) -> None:
        self.components.append(component)

    def render_html(self) -> str:
        body = "".join(c.render() for c in self.components)
        return f'<div style="max-width:{self.style_config.email_max_width}; margin:0 auto;">{body}</div>'


# =======================================
# SAMPLE DATA & DEMO
# =======================================

def create_sample_portfolio_data() -> pd.DataFrame:
    """Creates sample portfolio data."""
    dates = pd.date_range("2023-01-01", periods=5)
    return pd.DataFrame({
        "Date": dates,
        "Portfolio Value": np.random.uniform(90000, 110000, len(dates)),
        "Daily Return %": np.random.uniform(-0.03, 0.03, len(dates)),
        "Benchmark Return %": np.random.uniform(-0.02, 0.02, len(dates)),
    })


def demo_professional_report() -> str:
    """Generates a sample professional report HTML."""
    email_cfg = EmailConfig(sender="analyst@company.com", recipients=["team@company.com"], subject="Portfolio Update")
    style_cfg = StyleConfig()

    report = EmailReport(email_cfg, style_cfg)
    report.add_component(TextComponent("# Portfolio Performance Report\nGenerated automatically.", style_cfg))

    df = create_sample_portfolio_data()
    report.add_component(StyledTableComponent(df, style_cfg))

    if HAS_PLOTLY:
        fig = px.line(df, x="Date", y="Portfolio Value", title="Portfolio Value Over Time")
        report.add_component(PlotlyChartComponent(fig, style_cfg))

    return report.render_html()


if __name__ == "__main__":
    print(demo_professional_report())
