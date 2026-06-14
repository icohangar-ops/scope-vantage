"""
IntelligenceService — composite scoring + Bedrock AI analysis.
Score: Supply Risk 30% + Price Volatility 25% + Logistics Risk 25% + Policy Risk 20%.
"""
from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.analytics import pricing_risk
from src.models.intelligence_briefing import IntelligenceBriefing

load_dotenv()
logger = logging.getLogger(__name__)

SCORE_WEIGHTS = {"supply_risk": 0.30, "price_volatility": 0.25, "logistics_risk": 0.25, "policy_risk": 0.20}

SYSTEM_PROMPT = """You are a senior supply chain intelligence analyst. You analyze global trade flows,
commodity markets, logistics networks, and trade policy to provide actionable intelligence.
Focus on risks, opportunities, and strategic recommendations. Be data-driven and concise."""


class IntelligenceService:
    """Composite supply chain intelligence scoring and Bedrock AI analysis."""

    def __init__(self, bedrock_client: Optional[Any] = None) -> None:
        if bedrock_client is None:
            from bedrock_client import BedrockClient
            self._client = BedrockClient()
        else:
            self._client = bedrock_client
        self._supply_svc = None
        self._pricing_svc = None
        self._tariff_svc = None

    def set_services(self, supply_svc: Any = None, pricing_svc: Any = None, tariff_svc: Any = None) -> None:
        self._supply_svc = supply_svc
        self._pricing_svc = pricing_svc
        self._tariff_svc = tariff_svc

    def compute_composite_score(
        self, commodity: str,
        supply_risk: float = 50.0, price_volatility: float = 50.0,
        logistics_risk: float = 50.0, policy_risk: float = 50.0,
    ) -> Dict[str, Any]:
        """Compute weighted composite supply chain risk score (0-100)."""
        composite = (
            supply_risk * SCORE_WEIGHTS["supply_risk"]
            + price_volatility * SCORE_WEIGHTS["price_volatility"]
            + logistics_risk * SCORE_WEIGHTS["logistics_risk"]
            + policy_risk * SCORE_WEIGHTS["policy_risk"]
        )
        return {
            "commodity": commodity,
            "supply_risk": round(supply_risk, 1),
            "price_volatility": round(price_volatility, 1),
            "logistics_risk": round(logistics_risk, 1),
            "policy_risk": round(policy_risk, 1),
            "composite_score": round(composite, 1),
            "risk_level": "High" if composite >= 70 else "Medium" if composite >= 40 else "Low",
        }

    def compute_contract_risk(
        self,
        commodity: str,
        contract_price: float,
        market_price: float,
        volume: float,
        volatility: float,
        confidence_level: float = 0.95,
        time_horizon_days: float = 1.0,
        breach_threshold_pct: float = 10.0,
    ) -> Dict[str, Any]:
        """Quantitative risk profile for a commodity supply-chain contract.

        Combines mark-to-market P&L, parametric VaR/CVaR, a crisis-scenario
        stressed VaR, and the probability of price breaching a contract
        threshold. Position value is taken as the notional market exposure
        (|market_price * volume|).

        Args:
            commodity: Commodity name (echoed into the result).
            contract_price: Original contracted price per unit.
            market_price: Current market price per unit.
            volume: Contracted volume in applicable units.
            volatility: Per-period (e.g. daily) volatility, decimal, for VaR.
            confidence_level: VaR/CVaR confidence level (default 0.95).
            time_horizon_days: VaR holding period in days (default 1).
            breach_threshold_pct: Breach threshold as a percent move.

        Returns:
            Dict of quantitative risk metrics, all in USD unless noted.
        """
        position_value = abs(market_price * volume)
        pnl = pricing_risk.calculate_contract_pnl(contract_price, market_price, volume)
        var = pricing_risk.calculate_var(
            position_value, volatility, confidence_level, time_horizon_days
        )
        cvar = pricing_risk.calculate_cvar(position_value, volatility, confidence_level)
        stressed = pricing_risk.stress_test_var(position_value, volatility, 5.0)
        # breach_probability expects an annualized vol; de-scale the per-day input.
        annualized_vol = volatility * (pricing_risk.TRADING_DAYS ** 0.5)
        breach = pricing_risk.breach_probability(
            annualized_vol, breach_threshold_pct, time_horizon_days
        )
        return {
            "commodity": commodity,
            "position_value": round(position_value, 2),
            "mark_to_market_pnl": pnl,
            "value_at_risk": var,
            "conditional_var": cvar,
            "stressed_var_crisis": stressed,
            "breach_probability": breach,
            "confidence_level": confidence_level,
        }

    def generate_briefing(self, commodity: str, context: Dict = None) -> IntelligenceBriefing:
        """Generate full AI intelligence briefing via Bedrock Converse API."""
        prompt = f"""Analyze the supply chain intelligence for {commodity}:

Provide:
1. Key supply chain risks (concentration, geopolitical, logistics)
2. Price trend outlook
3. Trade policy impact assessment
4. Strategic recommendations for supply chain resilience
"""

        if context:
            prompt += f"\nContext data:\n{json.dumps(context, indent=2, default=str)}\n"

        try:
            analysis = self._client.chat(prompt, system=SYSTEM_PROMPT, max_tokens=800)
        except Exception as e:
            logger.error(f"Bedrock briefing failed for {commodity}: {e}")
            analysis = f"Analysis unavailable: {str(e)}"

        briefing = IntelligenceBriefing(
            scope="commodity",
            scope_value=commodity,
            summary=analysis[:2000],
            confidence_score=0.7 if context else 0.4,
            source_data_references=["comtradeapicall", "alpha_vantage", "fred"] if context else [],
        )
        return briefing
