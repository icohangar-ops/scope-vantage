"""
LogisticsEvent domain model — shipping, delays, disruptions, bottlenecks.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional


class EventType(str, Enum):
    SHIPMENT = "Shipment"
    DELAY = "Delay"
    DISRUPTION = "Disruption"
    BOTTLENECK = "Bottleneck"


class ImpactSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass
class LogisticsEvent:
    """Logistics event tracking."""
    event_id: str = ""
    event_type: EventType = EventType.SHIPMENT
    route: str = ""
    origin: str = ""
    destination: str = ""
    carrier: str = ""
    commodity: str = ""
    status: str = "Active"
    estimated_delay_days: float = 0.0
    impact_severity: ImpactSeverity = ImpactSeverity.LOW
    description: str = ""
    reported_at: str = ""
    resolved_at: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"EVT_{self.event_type.value}_{self.origin}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    @property
    def cost_impact_estimate(self) -> float:
        """Rough cost impact estimate based on severity and delay."""
        daily_cost = {"Low": 10000, "Medium": 50000, "High": 200000, "Critical": 1000000}
        base = daily_cost.get(self.impact_severity.value, 10000)
        return base * self.estimated_delay_days

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id, "event_type": self.event_type.value,
            "route": self.route, "origin": self.origin, "destination": self.destination,
            "carrier": self.carrier, "commodity": self.commodity, "status": self.status,
            "estimated_delay_days": self.estimated_delay_days,
            "impact_severity": self.impact_severity.value,
            "cost_impact_estimate": self.cost_impact_estimate,
            "description": self.description, "reported_at": self.reported_at,
            "resolved_at": self.resolved_at, "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> LogisticsEvent:
        for field_name, enum_cls in [("event_type", EventType), ("impact_severity", ImpactSeverity)]:
            if field_name in d and isinstance(d[field_name], str):
                d[field_name] = enum_cls(d[field_name])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return f"LogisticsEvent({self.event_type.value}, {self.origin}→{self.destination}, severity={self.impact_severity.value})"
