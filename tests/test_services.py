"""Tests for ComtradeService, PricingService, SupplyChainService, TariffService, IntelligenceService."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.services.comtrade_service import ComtradeService
from src.models.trade_flow import TradeFlow, TradeDirection
from src.services.pricing_service import PricingService
from src.services.supply_chain_service import SupplyChainService
from src.models.supply_chain_node import SupplyChainNode, NodeType
from src.services.tariff_service import TariffService
from src.models.tariff_regulation import TariffRegulation, RegulationType, RegulationStatus
from src.services.intelligence_service import IntelligenceService, SCORE_WEIGHTS


@pytest.fixture
def mock_bedrock():
    client = MagicMock()
    client.chat.return_value = "Lithium supply is concentrated in Australia and Chile. Key risks include Chinese processing dominance and EV demand volatility."
    return client


class TestComtradeService:
    def test_init(self):
        svc = ComtradeService(subscription_key="test_key")
        assert svc.subscription_key == "test_key"

    def test_normalize_hs(self):
        assert ComtradeService._normalize_hs("283690") == "2836.90"
        assert ComtradeService._normalize_hs("2836.90") == "2836.90"
        assert ComtradeService._normalize_hs("2836") == "2836.00"

    @patch("src.services.comtrade_service.ComtradeService._throttle")
    def test_fetch_no_library(self, mock_throttle):
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            svc = ComtradeService()
            flows = svc.fetch_trade_flows("China", "US", "7504.00", 2023)
            assert flows == []

    def test_country_codes(self):
        svc = ComtradeService()
        assert svc.get_country_code("China") == 156
        assert svc.get_country_code("United States") == 842
        assert svc.get_country_code("Nonexistent") is None

    def test_critical_mineral_hs_codes(self):
        from src.services.comtrade_service import MINERAL_HS_CODES
        assert len(MINERAL_HS_CODES) == 8
        assert "2836.90" in MINERAL_HS_CODES


class TestPricingService:
    def test_init(self):
        svc = PricingService(av_key="av_test", fred_key="fred_test")
        assert svc.av_key == "av_test"

    @patch.object(PricingService, "get_alpha_vantage_price", return_value=18000.0)
    def test_get_commodity_price_av(self, mock_av):
        svc = PricingService(av_key="key")
        price = svc.get_commodity_price("Copper")
        assert price == 18000.0

    @patch.object(PricingService, "get_alpha_vantage_price", return_value=None)
    @patch.object(PricingService, "get_fred_price", return_value=9500.0)
    def test_get_commodity_price_fred_fallback(self, mock_fred, mock_av):
        svc = PricingService(fred_key="key")
        price = svc.get_commodity_price("copper")
        assert price == 9500.0

    def test_get_commodity_price_no_source(self):
        svc = PricingService()
        price = svc.get_commodity_price("Lithium")
        assert price is None

    @patch("src.services.pricing_service.requests.Session.get")
    def test_av_rate_limit(self, mock_get):
        svc = PricingService(av_key="key")
        svc._av_calls = 25
        price = svc.get_alpha_vantage_price("COPPER")
        assert price is None

    def test_fred_no_key(self):
        import os
        old_key = os.environ.pop("FRED_API_KEY", None)
        try:
            svc = PricingService()
            assert svc.fred_key == ""
            assert svc.get_fred_price("WPU102501") is None
        finally:
            if old_key:
                os.environ["FRED_API_KEY"] = old_key

    @patch("src.services.pricing_service.requests.Session.get")
    def test_fred_with_key(self, mock_get):
        mock_get.return_value.json.return_value = {"observations": [{"value": "9500.0"}]}
        svc = PricingService(fred_key="test")
        price = svc.get_fred_price("WPU102501")
        assert price == 9500.0


class TestSupplyChainService:
    @pytest.fixture
    def chain(self):
        svc = SupplyChainService()
        svc.add_node(SupplyChainNode(node_id="aus_mine", name="GEM", country="Australia",
                                     node_type=NodeType.ORIGIN_COUNTRY, commodities=["Lithium"], capacity_share=55))
        svc.add_node(SupplyChainNode(node_id="cn_processor", name="CATL", country="China",
                                     node_type=NodeType.PROCESSING_HUB, commodities=["Lithium"], capacity_share=60))
        svc.add_node(SupplyChainNode(node_id="us_market", name="Tesla", country="US",
                                     node_type=NodeType.MANUFACTURER, commodities=["Lithium"]))
        svc.add_node(SupplyChainNode(node_id="eu_market", name="EU", country="Germany",
                                     node_type=NodeType.END_MARKET, commodities=["Lithium"]))
        svc.add_edge("aus_mine", "cn_processor")
        svc.add_edge("cn_processor", "us_market")
        svc.add_edge("cn_processor", "eu_market")
        return svc

    def test_add_node(self, chain):
        assert chain.get_node("aus_mine") is not None

    def test_get_by_type(self, chain):
        origins = chain.get_nodes_by_type(NodeType.ORIGIN_COUNTRY)
        assert len(origins) == 1

    def test_get_by_country(self, chain):
        china = chain.get_nodes_by_country("China")
        assert len(china) == 1

    def test_hhi_concentrated(self):
        hhi = SupplyChainService.compute_hhi({"Australia": 55, "Chile": 30, "China": 15})
        assert hhi > 2500
        assert SupplyChainService.interpret_hhi(hhi) == "Highly Concentrated"

    def test_hhi_unconcentrated(self):
        hhi = SupplyChainService.compute_hhi({"A": 20, "B": 20, "C": 20, "D": 20, "E": 20})
        # 5 equal shares: HHI = 5 * 0.20^2 * 10000 = 2000 (Moderately Concentrated)
        assert 1500 < hhi < 2500
        assert SupplyChainService.interpret_hhi(hhi) == "Moderately Concentrated"

    def test_hhi_empty(self):
        assert SupplyChainService.compute_hhi({}) == 0.0

    def test_compute_node_risk(self, chain):
        risk = chain.compute_node_risk("aus_mine")
        assert risk > 50  # High capacity + origin

    def test_detect_bottlenecks(self, chain):
        bottlenecks = chain.detect_bottlenecks()
        assert len(bottlenecks) > 0
        # China processor has 60% capacity = concentration bottleneck
        assert any(b["node_id"] == "cn_processor" for b in bottlenecks)

    def test_build_chain(self, chain):
        paths = chain.build_chain("Lithium")
        assert len(paths) >= 1
        # Path should go aus → cn → us/eu
        assert paths[0][0] == "aus_mine"


class TestTariffService:
    @pytest.fixture
    def svc(self):
        svc = TariffService()
        svc.load_regulations([
            TariffRegulation(regulation_type=RegulationType.TARIFF, imposing_country="US", target_country="China",
                              commodity_code="2836.90", rate_percent=25, status=RegulationStatus.ACTIVE),
            TariffRegulation(regulation_type=RegulationType.TARIFF, imposing_country="EU", target_country="Russia",
                              commodity_code="7504.00", rate_percent=15, status=RegulationStatus.ACTIVE),
            TariffRegulation(regulation_type=RegulationType.SANCTION, imposing_country="US", target_country="Russia",
                              status=RegulationStatus.ACTIVE),
            TariffRegulation(regulation_type=RegulationType.TARIFF, imposing_country="US", target_country="China",
                              commodity_code="8105.20", rate_percent=10, status=RegulationStatus.EXPIRED),
        ])
        return svc

    def test_get_active_tariffs(self, svc):
        active = svc.get_active_tariffs("2836.90")
        assert len(active) == 1
        assert active[0].rate_percent == 25

    def test_get_active_tariffs_all(self, svc):
        active = svc.get_active_tariffs()
        assert len(active) == 2  # 2 active tariffs (1 expired)

    def test_effective_tariff_rate(self, svc):
        rate = svc.get_effective_tariff_rate("2836.90", "China", "US")
        assert rate == 25.0

    def test_effective_tariff_rate_no_match(self, svc):
        rate = svc.get_effective_tariff_rate("9999.99", "Brazil", "US")
        assert rate == 0.0

    def test_quantify_impact(self, svc):
        tariff = svc.get_active_tariffs("2836.90")[0]
        impact = svc.quantify_impact(tariff, 1_000_000_000)
        assert impact["annual_tariff_cost"] == 250_000_000.0

    def test_scenario_new_tariff(self, svc):
        result = svc.scenario_new_tariff("Lithium Carbonate", "China", "US", 25, 2_000_000_000)
        assert result["estimated_annual_cost"] == 500_000_000.0

    def test_scenario_removal(self, svc):
        result = svc.scenario_removal("Nickel", "Russia", "EU", 15, 500_000_000)
        assert result["estimated_annual_savings"] == 75_000_000.0

    def test_trade_diversion(self, svc):
        alts = svc.analyze_trade_diversion("Lithium", "China", 25, [
            {"partner": "Chile", "tariff_rate": 0, "capacity_share": 30},
            {"partner": "Australia", "tariff_rate": 0, "capacity_share": 55},
        ])
        assert len(alts) == 2
        assert alts[0]["diversion_likelihood"] == "High"


class TestIntelligenceService:
    def test_composite_score(self, mock_bedrock):
        svc = IntelligenceService(bedrock_client=mock_bedrock)
        result = svc.compute_composite_score("Lithium", supply_risk=90, price_volatility=80, logistics_risk=85, policy_risk=90)
        assert result["composite_score"] > 80
        assert result["risk_level"] == "High"

    def test_composite_score_low(self, mock_bedrock):
        svc = IntelligenceService(bedrock_client=mock_bedrock)
        result = svc.compute_composite_score("Copper", supply_risk=10, price_volatility=10, logistics_risk=10, policy_risk=10)
        assert result["composite_score"] < 20
        assert result["risk_level"] == "Low"

    def test_score_weights(self):
        total = sum(SCORE_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_generate_briefing(self, mock_bedrock):
        svc = IntelligenceService(bedrock_client=mock_bedrock)
        briefing = svc.generate_briefing("Lithium", context={"hhi": 4200, "top_producer": "Australia"})
        assert briefing.scope_value == "Lithium"
        assert "Lithium" in briefing.summary
        assert briefing.confidence_score > 0

    def test_generate_briefing_error(self, mock_bedrock):
        mock_bedrock.chat.side_effect = Exception("Bedrock error")
        svc = IntelligenceService(bedrock_client=mock_bedrock)
        briefing = svc.generate_briefing("Nickel")
        assert "unavailable" in briefing.summary.lower()

    def test_set_services(self, mock_bedrock):
        svc = IntelligenceService(bedrock_client=mock_bedrock)
        svc.set_services(supply_svc=MagicMock())
        assert svc._supply_svc is not None
