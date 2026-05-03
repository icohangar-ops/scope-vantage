"""
Commodity domain model — commodity tracking linked to HS codes and pricing.
Categories: critical mineral, energy, agricultural, industrial.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional


class CommodityCategory(str, Enum):
    CRITICAL_MINERAL = "Critical Mineral"
    ENERGY = "Energy"
    AGRICULTURAL = "Agricultural"
    INDUSTRIAL = "Industrial"


# Critical minerals with HS codes
CRITICAL_MINERALS = {
    "2836.90": {"name": "Lithium Carbonate", "category": CommodityCategory.CRITICAL_MINERAL},
    "8105.20": {"name": "Cobalt", "category": CommodityCategory.CRITICAL_MINERAL},
    "7504.00": {"name": "Nickel", "category": CommodityCategory.CRITICAL_MINERAL},
    "7403.11": {"name": "Copper", "category": CommodityCategory.CRITICAL_MINERAL},
    "2846.90": {"name": "Rare Earth", "category": CommodityCategory.CRITICAL_MINERAL},
    "2601.20": {"name": "Iron Ore", "category": CommodityCategory.CRITICAL_MINERAL},
    "2616.10": {"name": "Silver Ore", "category": CommodityCategory.CRITICAL_MINERAL},
    "7202.60": {"name": "Manganese", "category": CommodityCategory.CRITICAL_MINERAL},
    "8104.20": {"name": "Magnesium", "category": CommodityCategory.CRITICAL_MINERAL},
    "8112.19": {"name": "Graphite", "category": CommodityCategory.CRITICAL_MINERAL},
}


@dataclass
class Commodity:
    """Commodity tracking with HS code linkage."""
    commodity_id: str = ""
    hs_code: str = ""
    name: str = ""
    category: CommodityCategory = CommodityCategory.CRITICAL_MINERAL
    current_price_usd: float = 0.0
    price_source: str = ""
    price_trend_30d: float = 0.0
    unit: str = "USD/tonne"
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.commodity_id and self.hs_code:
            self.commodity_id = f"CMD_{self.hs_code.replace('.', '')}"

    def to_dict(self) -> Dict:
        return {
            "commodity_id": self.commodity_id, "hs_code": self.hs_code, "name": self.name,
            "category": self.category.value, "current_price_usd": self.current_price_usd,
            "price_source": self.price_source, "price_trend_30d": self.price_trend_30d,
            "unit": self.unit, "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Commodity:
        if "category" in d and isinstance(d["category"], str):
            d["category"] = CommodityCategory(d["category"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def get_critical_minerals(cls) -> list:
        return [cls(hs_code=hs, name=meta["name"], category=meta["category"]) for hs, meta in CRITICAL_MINERALS.items()]

    def __repr__(self) -> str:
        return f"Commodity({self.name}, HS:{self.hs_code}, ${self.current_price_usd})"
