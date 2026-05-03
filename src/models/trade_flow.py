"""
TradeFlow domain model — UN Comtrade trade flow records.

Tracks bilateral trade flows with HS6 commodity codes,
unit conversions (kg→tonnes), and source attribution.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional


class TradeDirection(str, Enum):
    IMPORT = "Import"
    EXPORT = "Export"


@dataclass
class TradeFlow:
    """UN Comtrade trade flow record."""
    flow_id: str = ""
    reporter_code: str = ""
    reporter_name: str = ""
    partner_code: str = ""
    partner_name: str = ""
    commodity_code: str = ""
    commodity_name: str = ""
    trade_direction: TradeDirection = TradeDirection.IMPORT
    year: int = 0
    period: str = ""
    net_weight_kg: float = 0.0
    trade_value_usd: float = 0.0
    unit: str = "kg"
    source: str = "UN Comtrade"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.flow_id:
            self.flow_id = self._generate_id()

    def _generate_id(self) -> str:
        return f"{self.reporter_code}_{self.partner_code}_{self.commodity_code}_{self.year}_{self.trade_direction.value}"

    # --- Conversions ---
    @property
    def net_weight_tonnes(self) -> float:
        return self.net_weight_kg / 1000.0

    @property
    def unit_value_usd_per_kg(self) -> float:
        return self.trade_value_usd / self.net_weight_kg if self.net_weight_kg > 0 else 0.0

    @property
    def unit_value_usd_per_tonne(self) -> float:
        return self.trade_value_usd / self.net_weight_tonnes if self.net_weight_tonnes > 0 else 0.0

    # --- Serialization ---
    def to_dict(self) -> Dict:
        return {
            "flow_id": self.flow_id, "reporter_code": self.reporter_code, "reporter_name": self.reporter_name,
            "partner_code": self.partner_code, "partner_name": self.partner_name,
            "commodity_code": self.commodity_code, "commodity_name": self.commodity_name,
            "trade_direction": self.trade_direction.value, "year": self.year, "period": self.period,
            "net_weight_kg": self.net_weight_kg, "trade_value_usd": self.trade_value_usd,
            "unit": self.unit, "source": self.source, "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> TradeFlow:
        if "trade_direction" in d and isinstance(d["trade_direction"], str):
            d["trade_direction"] = TradeDirection(d["trade_direction"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return f"TradeFlow({self.reporter_name} → {self.partner_name}, {self.commodity_code}, {self.year}, {self.trade_direction.value})"
