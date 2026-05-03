"""
SupplyChainNode domain model — nodes in a supply chain graph.
Types: origin_country, processing_hub, manufacturer, end_market.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class NodeType(str, Enum):
    ORIGIN_COUNTRY = "Origin Country"
    PROCESSING_HUB = "Processing Hub"
    MANUFACTURER = "Manufacturer"
    END_MARKET = "End Market"


@dataclass
class SupplyChainNode:
    """A node in the supply chain graph."""
    node_id: str = ""
    node_type: NodeType = NodeType.ORIGIN_COUNTRY
    name: str = ""
    country: str = ""
    region: str = ""
    role: str = ""
    connected_to: List[str] = field(default_factory=list)
    risk_score: float = 50.0
    commodities: List[str] = field(default_factory=list)
    capacity_share: float = 0.0  # % of global capacity
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.node_id:
            self.node_id = f"{self.country}_{self.node_type.value.replace(' ', '_')}_{self.name}".strip("_")

    def add_connection(self, node_id: str) -> None:
        if node_id not in self.connected_to:
            self.connected_to.append(node_id)

    @property
    def risk_rating(self) -> str:
        if self.risk_score >= 75:
            return "High"
        elif self.risk_score >= 50:
            return "Medium"
        return "Low"

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id, "node_type": self.node_type.value, "name": self.name,
            "country": self.country, "region": self.region, "role": self.role,
            "connected_to": self.connected_to, "risk_score": self.risk_score,
            "risk_rating": self.risk_rating, "commodities": self.commodities,
            "capacity_share": self.capacity_share, "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> SupplyChainNode:
        if "node_type" in d and isinstance(d["node_type"], str):
            d["node_type"] = NodeType(d["node_type"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return f"SupplyChainNode({self.name}, {self.country}, {self.node_type.value}, risk={self.risk_score})"
