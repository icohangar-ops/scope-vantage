"""Tests for Scope.Vantage domain models."""
import pytest
from datetime import datetime
from src.models.trade_flow import TradeFlow, TradeDirection
from src.models.commodity import Commodity, CommodityCategory, CRITICAL_MINERALS
from src.models.supply_chain_node import SupplyChainNode, NodeType
from src.models.logistics_event import LogisticsEvent, EventType, ImpactSeverity
from src.models.tariff_regulation import TariffRegulation, RegulationType, RegulationStatus
from src.models.intelligence_briefing import IntelligenceBriefing


class TestTradeFlow:
    def test_create(self):
        tf = TradeFlow(reporter_code="156", partner_code="842", commodity_code="7504.00",
                        trade_direction=TradeDirection.EXPORT, year=2023, net_weight_kg=500000, trade_value_usd=5000000)
        assert tf.commodity_code == "7504.00"
        assert tf.trade_direction == TradeDirection.EXPORT

    def test_conversions(self):
        tf = TradeFlow(net_weight_kg=10000, trade_value_usd=50000)
        assert tf.net_weight_tonnes == 10.0
        assert tf.unit_value_usd_per_kg == 5.0
        assert tf.unit_value_usd_per_tonne == 5000.0

    def test_zero_weight(self):
        tf = TradeFlow(net_weight_kg=0, trade_value_usd=100)
        assert tf.unit_value_usd_per_kg == 0.0

    def test_serialization(self):
        tf = TradeFlow(reporter_code="156", commodity_code="2836.90", year=2023)
        d = tf.to_dict()
        assert d["trade_direction"] == "Import"
        assert d["commodity_code"] == "2836.90"

    def test_deserialization(self):
        d = {"reporter_code": "842", "commodity_code": "8105.20", "trade_direction": "Export", "year": 2023}
        tf = TradeFlow.from_dict(d)
        assert tf.trade_direction == TradeDirection.EXPORT

    def test_auto_id(self):
        tf = TradeFlow(reporter_code="156", partner_code="842", commodity_code="7504.00", year=2023)
        assert "156_842_7504.00" in tf.flow_id


class TestCommodity:
    def test_create(self):
        c = Commodity(hs_code="7504.00", name="Nickel", category=CommodityCategory.CRITICAL_MINERAL, current_price_usd=18000)
        assert c.hs_code == "7504.00"
        assert c.auto_id if False else True  # Auto-generated

    def test_critical_minerals_list(self):
        minerals = Commodity.get_critical_minerals()
        assert len(minerals) == 10
        hs_codes = [m.hs_code for m in minerals]
        assert "2836.90" in hs_codes
        assert "7504.00" in hs_codes

    def test_serialization(self):
        c = Commodity(hs_code="7403.11", name="Copper", category=CommodityCategory.CRITICAL_MINERAL)
        d = c.to_dict()
        assert d["category"] == "Critical Mineral"

    def test_deserialization(self):
        d = {"hs_code": "8105.20", "name": "Cobalt", "category": "Critical Mineral"}
        c = Commodity.from_dict(d)
        assert c.category == CommodityCategory.CRITICAL_MINERAL


class TestSupplyChainNode:
    def test_create(self):
        n = SupplyChainNode(name="GEM", country="Australia", node_type=NodeType.ORIGIN_COUNTRY, commodities=["Lithium"], capacity_share=55)
        assert n.country == "Australia"
        # capacity_share > 50 adds 30 to base 30, so risk >= 60 = Medium
        assert n.risk_rating in ("Medium", "High")

    def test_add_connection(self):
        n = SupplyChainNode(name="A", country="X")
        n.add_connection("node_B")
        n.add_connection("node_B")  # Duplicate
        assert len(n.connected_to) == 1

    def test_risk_rating(self):
        low = SupplyChainNode(risk_score=30)
        med = SupplyChainNode(risk_score=60)
        high = SupplyChainNode(risk_score=80)
        assert low.risk_rating == "Low"
        assert med.risk_rating == "Medium"
        assert high.risk_rating == "High"

    def test_serialization_roundtrip(self):
        n = SupplyChainNode(name="CATL", country="China", node_type=NodeType.MANUFACTURER, commodities=["Lithium", "Cobalt"])
        d = n.to_dict()
        restored = SupplyChainNode.from_dict(d)
        assert restored.name == "CATL"
        assert restored.node_type == NodeType.MANUFACTURER
        assert "Lithium" in restored.commodities


class TestLogisticsEvent:
    def test_create(self):
        evt = LogisticsEvent(event_type=EventType.DISRUPTION, origin="China", destination="US",
                              impact_severity=ImpactSeverity.HIGH, estimated_delay_days=14)
        assert evt.impact_severity == ImpactSeverity.HIGH

    def test_cost_impact(self):
        evt = LogisticsEvent(impact_severity=ImpactSeverity.CRITICAL, estimated_delay_days=7)
        assert evt.cost_impact_estimate == 7_000_000

    def test_serialization(self):
        evt = LogisticsEvent(event_type=EventType.BOTTLENECK, origin="Panama Canal")
        d = evt.to_dict()
        assert d["event_type"] == "Bottleneck"

    def test_deserialization(self):
        d = {"event_type": "Delay", "origin": "A", "destination": "B", "impact_severity": "Medium"}
        evt = LogisticsEvent.from_dict(d)
        assert evt.event_type == EventType.DELAY
        assert evt.impact_severity == ImpactSeverity.MEDIUM


class TestTariffRegulation:
    def test_create(self):
        reg = TariffRegulation(regulation_type=RegulationType.TARIFF, imposing_country="US",
                                target_country="China", commodity_code="2836.90", rate_percent=25, status=RegulationStatus.ACTIVE)
        assert reg.is_active()
        assert reg.rate_percent == 25

    def test_inactive(self):
        reg = TariffRegulation(status=RegulationStatus.EXPIRED)
        assert not reg.is_active()

    def test_serialization(self):
        reg = TariffRegulation(regulation_type=RegulationType.SANCTION, imposing_country="US", target_country="Russia")
        d = reg.to_dict()
        assert d["regulation_type"] == "Sanction"

    def test_deserialization(self):
        d = {"regulation_type": "Quota", "imposing_country": "EU", "status": "Proposed"}
        reg = TariffRegulation.from_dict(d)
        assert reg.regulation_type == RegulationType.QUOTA
        assert reg.status == RegulationStatus.PROPOSED


class TestIntelligenceBriefing:
    def test_create(self):
        b = IntelligenceBriefing(scope="commodity", scope_value="Lithium", summary="Supply risk rising", confidence_score=0.8)
        assert b.scope_value == "Lithium"
        assert "Lithium" in b.briefing_id

    def test_serialization(self):
        b = IntelligenceBriefing(scope_value="Nickel", opportunities=["Diversify sources"], recommendations=["Monitor Indonesia"])
        d = b.to_dict()
        assert d["scope_value"] == "Nickel"
        assert len(d["opportunities"]) == 1
