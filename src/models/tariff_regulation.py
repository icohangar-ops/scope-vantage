"""
TariffRegulation domain model — tariffs, quotas, sanctions, embargoes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional


class RegulationType(str, Enum):
    TARIFF = "Tariff"
    QUOTA = "Quota"
    SANCTION = "Sanction"
    EMBARGO = "Embargo"


class RegulationStatus(str, Enum):
    ACTIVE = "Active"
    PROPOSED = "Proposed"
    EXPIRED = "Expired"


@dataclass
class TariffRegulation:
    """Trade policy regulation."""
    reg_id: str = ""
    regulation_type: RegulationType = RegulationType.TARIFF
    imposing_country: str = ""
    target_country: str = ""
    commodity_code: str = ""
    commodity_name: str = ""
    rate_percent: float = 0.0
    effective_date: str = ""
    expiry_date: Optional[str] = None
    status: RegulationStatus = RegulationStatus.ACTIVE
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.reg_id:
            self.reg_id = f"REG_{self.imposing_country}_{self.target_country}_{self.commodity_code}".strip("_")

    def is_active(self) -> bool:
        return self.status == RegulationStatus.ACTIVE

    @property
    def annual_impact_estimate(self) -> float:
        """Rough annual trade impact based on rate and typical volumes."""
        return self.rate_percent * 1_000_000  # Simplified

    def to_dict(self) -> Dict:
        return {
            "reg_id": self.reg_id, "regulation_type": self.regulation_type.value,
            "imposing_country": self.imposing_country, "target_country": self.target_country,
            "commodity_code": self.commodity_code, "commodity_name": self.commodity_name,
            "rate_percent": self.rate_percent, "effective_date": self.effective_date,
            "expiry_date": self.expiry_date, "status": self.status.value,
            "description": self.description, "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> TariffRegulation:
        for field_name, enum_cls in [("regulation_type", RegulationType), ("status", RegulationStatus)]:
            if field_name in d and isinstance(d[field_name], str):
                d[field_name] = enum_cls(d[field_name])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return f"TariffRegulation({self.regulation_type.value}, {self.imposing_country}→{self.target_country}, {self.rate_percent}%)"
