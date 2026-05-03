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
