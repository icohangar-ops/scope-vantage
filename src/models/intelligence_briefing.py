"""
IntelligenceBriefing domain model — AI-generated supply chain intelligence.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class IntelligenceBriefing:
    """AI-generated intelligence briefing."""
    briefing_id: str = ""
    generated_at: datetime = field(default_factory=datetime.utcnow)
    scope: str = ""  # commodity, route, region
    scope_value: str = ""  # e.g. "Lithium", "China→US", "Southeast Asia"
    summary: str = ""
    risk_assessment: str = ""
    opportunities: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    source_data_references: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.briefing_id:
            ts = self.generated_at.strftime("%Y%m%d_%H%M%S")
            self.briefing_id = f"BRIEF_{self.scope_value.replace(' ', '_')}_{ts}"

    def to_dict(self) -> Dict:
        return {
            "briefing_id": self.briefing_id, "generated_at": self.generated_at.isoformat(),
            "scope": self.scope, "scope_value": self.scope_value, "summary": self.summary,
            "risk_assessment": self.risk_assessment, "opportunities": self.opportunities,
            "recommendations": self.recommendations, "confidence_score": self.confidence_score,
            "source_data_references": self.source_data_references,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> IntelligenceBriefing:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return f"IntelligenceBriefing({self.scope}: {self.scope_value}, confidence={self.confidence_score})"
