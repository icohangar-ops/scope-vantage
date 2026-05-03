"""
ComtradeService — UN Comtrade data ingestion via comtradeapicall library.

Fetches bilateral trade flows for critical minerals, normalizes units,
and caches results.
"""
from __future__ import annotations
import logging
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.models.trade_flow import TradeFlow, TradeDirection

logger = logging.getLogger(__name__)
load_dotenv()

# Critical mineral HS codes
MINERAL_HS_CODES = ["2836.90", "8105.20", "7504.00", "7403.11", "2846.90", "2601.20", "8112.19", "7202.60"]

# Key reporter/partner codes
COUNTRY_CODES = {
    "China": 156, "United States": 842, "Australia": 36, "Chile": 152,
    "DR Congo": 180, "Indonesia": 360, "Russia": 643, "Canada": 124,
    "Germany": 276, "Japan": 392, "South Korea": 410, "India": 356,
    "Brazil": 76, "Mexico": 484, "Vietnam": 704, "Philippines": 608,
}

HS_CODE_NAMES = {
    "2836.90": "Lithium Carbonate", "8105.20": "Cobalt", "7504.00": "Nickel",
    "7403.11": "Copper Refined", "2846.90": "Rare Earth Compounds",
    "2601.20": "Iron Ore", "8112.19": "Natural Graphite", "7202.60": "Manganese",
}


class ComtradeService:
    """Service for fetching UN Comtrade trade data."""

    def __init__(self, subscription_key: str = "") -> None:
        self.subscription_key = subscription_key or os.environ.get("UN_COMTRADE_KEY", "")
        self._last_call: float = 0.0
        self._min_interval: float = 1.0  # Rate limit
        self._cache: Dict[str, Any] = {}

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

    def fetch_trade_flows(
        self,
        reporter: str,
        partner: str,
        hs_code: str,
        year: int = 2023,
        direction: str = "all",
    ) -> List[TradeFlow]:
        """Fetch trade flows using comtradeapicall library."""
        self._throttle()

        reporter_code = COUNTRY_CODES.get(reporter, reporter)
        partner_code = COUNTRY_CODES.get(partner, partner)

        try:
            import comtradeapicall
            flows = []

            fetch_fn = comtradeapicall.getFinalData

            if direction in ("import", "all"):
                try:
                    import comtradeapicall as ct
                    if self.subscription_key:
                        ct.subscribeComtradeApi(self.subscription_key)
                    data = ct.getFinalData(
                        reporterCode=reporter_code,
                        partnerCode=partner_code if partner != "World" else 0,
                        freq="A", clCode="HS", cmdCode=hs_code.replace(".", ""),
                        flowCode="M", period=str(year),
                    )
                    if data and not data.empty:
                        for _, row in data.iterrows():
                            flows.append(self._row_to_trade_flow(row, TradeDirection.IMPORT, year))
                except Exception as e:
                    logger.warning(f"Comtrade import fetch failed: {e}")

            if direction in ("export", "all"):
                try:
                    import comtradeapicall as ct
                    data = ct.getFinalData(
                        reporterCode=reporter_code,
                        partnerCode=partner_code if partner != "World" else 0,
                        freq="A", clCode="HS", cmdCode=hs_code.replace(".", ""),
                        flowCode="X", period=str(year),
                    )
                    if data and not data.empty:
                        for _, row in data.iterrows():
                            flows.append(self._row_to_trade_flow(row, TradeDirection.EXPORT, year))
                except Exception as e:
                    logger.warning(f"Comtrade export fetch failed: {e}")

            return flows

        except ImportError:
            logger.error("comtradeapicall not installed. Run: pip install comtradeapicall")
            return []
        except Exception as e:
            logger.error(f"Comtrade fetch error: {e}")
            return []

    def _row_to_trade_flow(self, row: Any, direction: TradeDirection, year: int) -> TradeFlow:
        """Convert a comtradeapicall DataFrame row to TradeFlow."""
        reporter_code = str(getattr(row, "reporterCode", getattr(row, "reporter", "")))
        partner_code = str(getattr(row, "partnerCode", getattr(row, "partner", "")))
        cmd_code = str(getattr(row, "cmdCode", getattr(row, "commodity", "")))
        weight = float(getattr(row, "netWeightKg", getattr(row, "wt", 0) or 0))
        value = float(getattr(row, "tradeValue", getattr(row, "tradeValue", 0) or 0))

        # Normalize HS code format
        hs_normalized = self._normalize_hs(cmd_code)

        return TradeFlow(
            reporter_code=reporter_code,
            partner_code=partner_code,
            commodity_code=hs_normalized,
            commodity_name=HS_CODE_NAMES.get(hs_normalized, ""),
            trade_direction=direction,
            year=year,
            net_weight_kg=weight,
            trade_value_usd=value,
        )

    @staticmethod
    def _normalize_hs(code: str) -> str:
        """Normalize HS code to XXXX.XX format."""
        code = str(code).replace(".", "").strip()
        if len(code) == 6:
            return f"{code[:4]}.{code[4:]}"
        if len(code) == 4:
            return f"{code}.00"
        return code

    def fetch_critical_mineral_flows(
        self,
        reporter: str = "China",
        partner: str = "World",
        year: int = 2023,
    ) -> List[TradeFlow]:
        """Fetch all critical mineral trade flows for a country pair."""
        all_flows = []
        for hs in MINERAL_HS_CODES:
            flows = self.fetch_trade_flows(reporter, partner, hs, year)
            all_flows.extend(flows)
            logger.info(f"Fetched {len(flows)} flows for {hs} ({reporter}→{partner})")
        return all_flows

    def get_country_code(self, country_name: str) -> Optional[int]:
        return COUNTRY_CODES.get(country_name)
