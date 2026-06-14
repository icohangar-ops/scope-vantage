"""Polars-based data processing for Scope Vantage supply chain analytics.

Provides high-performance alternatives to pandas operations for large
commodity datasets. Polars is 10-100x faster for filtering, aggregation,
and time-series analysis on datasets with millions of rows.
"""
from __future__ import annotations

from typing import Any, Optional

try:
    import polars as pl
except ImportError:
    pl = None  # soft dependency


def require_polars() -> None:
    if pl is None:
        raise ImportError("polars is required: pip install polars")


class PolarsDataProcessor:
    """High-performance supply chain data processor using Polars."""

    def __init__(self, df: Any = None) -> None:
        require_polars()
        if df is not None:
            self.df = df if isinstance(df, pl.DataFrame) else pl.from_pandas(df)
        else:
            self.df = pl.DataFrame()

    def filter_by_commodity(self, commodity: str) -> "PolarsDataProcessor":
        if "commodity" in self.df.columns:
            return PolarsDataProcessor(self.df.filter(pl.col("commodity") == commodity))
        return self

    def filter_by_country(self, country: str) -> "PolarsDataProcessor":
        if "country" in self.df.columns:
            return PolarsDataProcessor(self.df.filter(pl.col("country") == country))
        return self

    def filter_by_date_range(self, start: str, end: str) -> "PolarsDataProcessor":
        date_col = next((c for c in self.df.columns if "date" in c.lower()), None)
        if date_col:
            return PolarsDataProcessor(
                self.df.filter(
                    (pl.col(date_col) >= start) & (pl.col(date_col) <= end)
                )
            )
        return self

    def aggregate_by_region(self, value_col: str = "trade_value") -> pl.DataFrame:
        if "region" in self.df.columns and value_col in self.df.columns:
            return self.df.group_by("region").agg(
                pl.col(value_col).sum().alias("total_value"),
                pl.len().alias("record_count"),
            )
        return self.df

    def aggregate_by_commodity(self, value_col: str = "trade_value") -> pl.DataFrame:
        if "commodity" in self.df.columns and value_col in self.df.columns:
            return self.df.group_by("commodity").agg(
                pl.col(value_col).sum().alias("total_value"),
                pl.col(value_col).mean().alias("avg_value"),
                pl.col(value_col).std().alias("std_value"),
            )
        return self.df

    def rolling_stats(self, value_col: str, window: int = 30) -> pl.DataFrame:
        date_col = next((c for c in self.df.columns if "date" in c.lower()), None)
        if date_col and value_col in self.df.columns:
            return self.df.sort(date_col).with_columns(
                pl.col(value_col).rolling_mean(window_size=window).alias(f"{value_col}_rolling_mean"),
                pl.col(value_col).rolling_std(window_size=window).alias(f"{value_col}_rolling_std"),
            )
        return self.df

    def compute_volatility(self, value_col: str, window: int = 30) -> pl.DataFrame:
        date_col = next((c for c in self.df.columns if "date" in c.lower()), None)
        if date_col and value_col in self.df.columns:
            sorted_df = self.df.sort(date_col)
            return sorted_df.with_columns(
                pl.col(value_col).pct_change().alias("_returns"),
            ).with_columns(
                pl.col("_returns").rolling_std(window_size=window).alias("volatility"),
            ).drop("_returns")
        return self.df

    def hhi_index(self, value_col: str, group_col: str) -> float:
        if value_col in self.df.columns and group_col in self.df.columns:
            shares = self.df.group_by(group_col).agg(pl.col(value_col).sum())
            total = shares[value_col].sum()
            if total > 0:
                market_shares = shares[value_col] / total
                return float((market_shares**2).sum())
        return 0.0

    def to_pandas(self) -> Any:
        return self.df.to_pandas()

    def quick_summary(self) -> dict[str, Any]:
        return {
            "rows": self.df.height,
            "columns": self.df.width,
            "column_names": self.df.columns,
        }


def compare_performance(polars_df: Any, pandas_df: Any) -> dict[str, Any]:
    """Compare Polars vs pandas performance on common operations."""
    import time

    results = {}
    for label, processor in [("polars", PolarsDataProcessor(polars_df)), ("pandas", None)]:
        start = time.time()
        if label == "polars":
            _ = processor.df.head(1000).to_pandas()
        else:
            _ = pandas_df.head(1000)
        results[f"{label}_head_ms"] = round((time.time() - start) * 1000, 2)

    return results
