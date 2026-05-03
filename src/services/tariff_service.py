"""
TariffService — trade policy analysis, impact quantification, scenario modeling.
"""
from __future__ import annotations
import logging
from typing import Dict, List, Optional

from src.models.tariff_regulation import TariffRegulation, RegulationType, RegulationStatus

logger = logging.getLogger(__name__)


class TariffService:
    """Trade policy analysis and scenario modeling."""

    def __init__(self) -> None:
        self._regulations: List[TariffRegulation] = []

    def load_regulations(self, regs: List[TariffRegulation]) -> None:
        self._regulations = regs

    def get_active_tariffs(self, commodity_code: str = "") -> List[TariffRegulation]:
        regs = [r for r in self._regulations if r.is_active() and r.regulation_type == RegulationType.TARIFF]
        if commodity_code:
            regs = [r for r in regs if r.commodity_code == commodity_code]
        return regs

    def get_effective_tariff_rate(self, commodity_code: str, from_country: str, to_country: str) -> float:
        """Get the highest applicable tariff rate for a trade flow."""
        applicable = [
            r for r in self._regulations
            if r.is_active()
            and r.regulation_type == RegulationType.TARIFF
            and r.imposing_country == to_country
            and r.target_country == from_country
            and (not commodity_code or r.commodity_code == commodity_code)
        ]
        return max((r.rate_percent for r in applicable), default=0.0)

    def quantify_impact(self, tariff: TariffRegulation, annual_trade_value_usd: float) -> Dict:
        """Quantify the financial impact of a tariff on trade."""
        annual_cost = annual_trade_value_usd * tariff.rate_percent / 100.0
        return {
            "tariff_id": tariff.reg_id,
            "rate_percent": tariff.rate_percent,
            "annual_trade_value": annual_trade_value_usd,
            "annual_tariff_cost": round(annual_cost, 2),
            "imposing_country": tariff.imposing_country,
            "target_country": tariff.target_country,
            "commodity": tariff.commodity_name,
        }

    def scenario_new_tariff(
        self, commodity: str, from_country: str, to_country: str,
        proposed_rate: float, annual_trade_value: float,
    ) -> Dict:
        """Model impact of a proposed new tariff."""
        return {
            "scenario": "New Tariff",
            "commodity": commodity,
            "from_country": from_country,
            "to_country": to_country,
            "proposed_rate_percent": proposed_rate,
            "annual_trade_value_usd": annual_trade_value,
            "estimated_annual_cost": round(annual_trade_value * proposed_rate / 100.0, 2),
            "price_impact_pct": round(proposed_rate * 0.6, 2),  # Approx pass-through
        }

    def scenario_removal(
        self, commodity: str, from_country: str, to_country: str,
        current_rate: float, annual_trade_value: float,
    ) -> Dict:
        """Model impact of removing an existing tariff."""
        return {
            "scenario": "Tariff Removal",
            "commodity": commodity,
            "from_country": from_country,
            "to_country": to_country,
            "removed_rate_percent": current_rate,
            "annual_trade_value_usd": annual_trade_value,
            "estimated_annual_savings": round(annual_trade_value * current_rate / 100.0, 2),
            "trade_volume_boost_estimate_pct": round(current_rate * 1.5, 2),
        }

    def analyze_trade_diversion(
        self, commodity: str, original_partner: str, tariff_to_original: float,
        alternative_partners: List[Dict],
    ) -> List[Dict]:
        """Analyze trade diversion when tariffs make original partner expensive."""
        results = []
        for alt in alternative_partners:
            alt_rate = alt.get("tariff_rate", 0)
            advantage = tariff_to_original - alt_rate
            results.append({
                "alternative_partner": alt.get("partner", ""),
                "tariff_rate_pct": alt_rate,
                "rate_advantage_pct": advantage,
                "estimated_capacity_share": alt.get("capacity_share", 0),
                "diversion_likelihood": "High" if advantage > 10 else "Medium" if advantage > 0 else "Low",
            })
        return sorted(results, key=lambda r: r["rate_advantage_pct"], reverse=True)
