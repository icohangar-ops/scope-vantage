"""
PricingService — AlphaVantage + FRED integration for commodity prices.
"""
from __future__ import annotations
import logging
import os
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)
AV_BASE = "https://www.alphavantage.co/query"
FRED_BASE = "https://api.stlouisfed.org/fred"

# Commodity → AlphaVantage function mapping
COMMODITY_SYMBOLS = {
    "Lithium": None,  # Not on AlphaVantage free
    "Cobalt": None,
    "Nickel": "NICKEL",
    "Copper": "COPPER",
    "Iron Ore": "IRON_ORE",
    "Silver": "SILVER",
    "Manganese": None,
    "Rare Earth": None,
    "Graphite": None,
}

FRED_COMMODITY_SERIES = {
    "copper": "WPU102501",  # Copper base metals
    "gold": "GOLDAMGBD228NLBM",  # Gold
    "silver": "SLVPRCD",  # Silver
}

class PricingService:
    """Commodity price data from AlphaVantage and FRED."""

    def __init__(self, av_key: str = "", fred_key: str = "") -> None:
        self.av_key = av_key or os.environ.get("ALPHA_VANTAGE_KEY", "")
        self.fred_key = fred_key or os.environ.get("FRED_API_KEY", "")
        self._session = requests.Session()
        self._av_calls = 0

    def get_alpha_vantage_price(self, symbol: str) -> Optional[float]:
        if self._av_calls >= 25 or not self.av_key:
            return None
        try:
            r = self._session.get(AV_BASE, params={
                "function": "COMMODITY_DAILY", "symbol": symbol,
                "apikey": self.av_key, "datatype": "json",
            }, timeout=30)
            self._av_calls += 1
            data = r.json()
            series = data.get("data", []) or []
            if not series:
                series = list(data.values())
                for v in series:
                    if isinstance(v, dict) and "value" in v:
                        series = list(v.values())
                        break
            # Look for latest price
            for item in (data.get("data", []) or []):
                if "value" in item:
                    return float(item["value"])
            return None
        except Exception as e:
            logger.error(f"AlphaVantage error for {symbol}: {e}")
            return None

    def get_fred_price(self, series_id: str) -> Optional[float]:
        if not self.fred_key:
            return None
        try:
            r = self._session.get(f"{FRED_BASE}/series/observations", params={
                "series_id": series_id, "api_key": self.fred_key,
                "file_type": "json", "sort_order": "desc", "limit": 1,
            }, timeout=30)
            data = r.json()
            obs = data.get("observations", [])
            if obs:
                val = obs[0].get("value", "0")
                return float(val) if val not in (".", "") else None
            return None
        except Exception as e:
            logger.error(f"FRED error for {series_id}: {e}")
            return None

    def get_commodity_price(self, commodity: str) -> Optional[float]:
        """Get best available price for a commodity."""
        # Try AlphaVantage first
        symbol = COMMODITY_SYMBOLS.get(commodity)
        if symbol:
            price = self.get_alpha_vantage_price(symbol)
            if price:
                return price
        # Try FRED
        series = FRED_COMMODITY_SERIES.get(commodity.lower())
        if series:
            price = self.get_fred_price(series)
            if price:
                return price
        return None
