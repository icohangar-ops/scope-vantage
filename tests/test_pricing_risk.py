"""Tests for src.analytics.pricing_risk — quantitative pricing & risk math.

Expected values are HAND-COMPUTED / anchored to textbook results, since this is
money/math code. Key anchors:
  * Black-Scholes ATM (S=K=100, T=1, r=0, vol=0.20) = 7.9656 (classic value).
  * Put-call parity: C - P = S - K*e^(-rT).
  * Parametric VaR = |V| * vol * z * sqrt(t); z(95%)=1.645.
"""
import math

import pytest

from src.analytics import pricing_risk as pr
from src.services.intelligence_service import IntelligenceService


# --------------------------------------------------------------------------- #
# Black-Scholes
# --------------------------------------------------------------------------- #
class TestBlackScholes:
    def test_atm_call_classic_value(self):
        # Famous closed-form result: 100*N(0.1) - 100*N(-0.1) = 7.9656.
        price = pr.black_scholes_price(100, 100, 1.0, 0.0, 0.20, "CALL")
        assert price == 7.9656

    def test_atm_put_equals_call_when_r_zero(self):
        # With r=0 and S=K, parity gives C = P.
        call = pr.black_scholes_price(100, 100, 1.0, 0.0, 0.20, "CALL")
        put = pr.black_scholes_price(100, 100, 1.0, 0.0, 0.20, "PUT")
        assert call == put == 7.9656

    def test_known_call_value(self):
        # S=75,K=80,T=0.25,r=0.05,vol=0.30 -> hand-computed 2.8742.
        assert pr.black_scholes_price(75, 80, 0.25, 0.05, 0.30, "CALL") == 2.8742

    def test_known_put_value(self):
        assert pr.black_scholes_price(75, 80, 0.25, 0.05, 0.30, "PUT") == 6.8805

    def test_put_call_parity(self):
        S, K, T, r, v = 75, 80, 0.25, 0.05, 0.30
        call = pr.black_scholes_price(S, K, T, r, v, "CALL")
        put = pr.black_scholes_price(S, K, T, r, v, "PUT")
        expected = S - K * math.exp(-r * T)
        assert call - put == pytest.approx(expected, abs=1e-3)

    def test_case_insensitive_option_type(self):
        assert pr.black_scholes_price(100, 100, 1.0, 0.0, 0.20, "call") == 7.9656

    def test_deep_itm_call_approaches_intrinsic(self):
        # Very high spot vs strike: price ~ spot - discounted strike.
        price = pr.black_scholes_price(1000, 100, 1.0, 0.0, 0.20, "CALL")
        assert price == pytest.approx(900.0, abs=1.0)

    def test_invalid_time(self):
        with pytest.raises(ValueError):
            pr.black_scholes_price(100, 100, 0.0, 0.0, 0.20, "CALL")

    def test_invalid_vol(self):
        with pytest.raises(ValueError):
            pr.black_scholes_price(100, 100, 1.0, 0.0, 0.0, "CALL")

    def test_invalid_spot(self):
        with pytest.raises(ValueError):
            pr.black_scholes_price(0, 100, 1.0, 0.0, 0.20, "CALL")

    def test_invalid_option_type(self):
        with pytest.raises(ValueError):
            pr.black_scholes_price(100, 100, 1.0, 0.0, 0.20, "STRADDLE")


# --------------------------------------------------------------------------- #
# Commodity pricing & P&L
# --------------------------------------------------------------------------- #
class TestCommodityPricing:
    def test_adjusted_price(self):
        # 75 * 1.05 * 1.02 + 2.50 = 82.825.
        assert pr.calculate_commodity_price(75.0, 0.05, 0.02, 2.50, 1.0) == 82.825

    def test_currency_adjustment(self):
        # base 100, no premiums, *1.10 FX = 110.0.
        assert pr.calculate_commodity_price(100.0, 0.0, 0.0, 0.0, 1.10) == 110.0

    def test_defaults_passthrough(self):
        assert pr.calculate_commodity_price(50.0) == 50.0

    def test_pnl_gain(self):
        # (80 - 75) * 10000 = 50000.
        assert pr.calculate_contract_pnl(75.0, 80.0, 10000) == 50000.0

    def test_pnl_loss(self):
        assert pr.calculate_contract_pnl(80.0, 75.0, 10000) == -50000.0

    def test_pnl_flat(self):
        assert pr.calculate_contract_pnl(80.0, 80.0, 10000) == 0.0


# --------------------------------------------------------------------------- #
# VaR / CVaR / stress
# --------------------------------------------------------------------------- #
class TestVaR:
    def test_var_95(self):
        # 1,000,000 * 0.02 * 1.645 * sqrt(1) = 32,900.
        assert pr.calculate_var(1_000_000, 0.02, 0.95, 1) == 32900.0

    def test_var_99(self):
        # 1,000,000 * 0.02 * 2.326 = 46,520.
        assert pr.calculate_var(1_000_000, 0.02, 0.99, 1) == 46520.0

    def test_var_time_scaling(self):
        # 10-day VaR = 1-day VaR * sqrt(10).
        one_day = pr.calculate_var(1_000_000, 0.02, 0.95, 1)
        ten_day = pr.calculate_var(1_000_000, 0.02, 0.95, 10)
        assert ten_day == pytest.approx(one_day * math.sqrt(10), abs=1.0)

    def test_var_uses_abs_position(self):
        # Short position (negative value) yields same loss magnitude.
        assert pr.calculate_var(-1_000_000, 0.02, 0.95, 1) == 32900.0

    def test_unknown_confidence_defaults_95(self):
        assert pr.calculate_var(1_000_000, 0.02, 0.5, 1) == 32900.0

    def test_cvar_exceeds_var(self):
        var = pr.calculate_var(1_000_000, 0.02, 0.95, 1)
        cvar = pr.calculate_cvar(1_000_000, 0.02, 0.95)
        assert cvar > var

    def test_cvar_95_closed_form(self):
        # ES = |V|*vol*pdf(z)/(1-c); z=1.645, pdf(1.645)=0.103295...
        z = 1.645
        pdf = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
        expected = round(1_000_000 * 0.02 * pdf / 0.05, 2)
        assert pr.calculate_cvar(1_000_000, 0.02, 0.95) == expected

    def test_stress_var_crisis(self):
        # 1,000,000 * 0.02 * 5.0 = 100,000.
        assert pr.stress_test_var(1_000_000, 0.02, 5.0) == 100000.0


# --------------------------------------------------------------------------- #
# Breach probability
# --------------------------------------------------------------------------- #
class TestBreachProbability:
    def test_known_breach(self):
        # vol=0.30, 10% threshold, 30 days -> 0.334 (hand-computed two-tailed).
        assert pr.breach_probability(0.30, 10.0, 30) == 0.334

    def test_higher_vol_higher_prob(self):
        low = pr.breach_probability(0.20, 10.0, 30)
        high = pr.breach_probability(0.60, 10.0, 30)
        assert high > low

    def test_longer_horizon_higher_prob(self):
        short = pr.breach_probability(0.30, 10.0, 5)
        long = pr.breach_probability(0.30, 10.0, 60)
        assert long > short

    def test_zero_vol_returns_zero(self):
        assert pr.breach_probability(0.0, 10.0, 30) == 0.0

    def test_zero_time_returns_zero(self):
        assert pr.breach_probability(0.30, 10.0, 0) == 0.0

    def test_bounded_0_1(self):
        p = pr.breach_probability(2.0, 0.1, 365)  # huge vol, tiny threshold
        assert 0.0 <= p <= 1.0


# --------------------------------------------------------------------------- #
# Historical VaR
# --------------------------------------------------------------------------- #
class TestHistoricalVaR:
    def test_empty_returns_zero(self):
        assert pr.historical_var([], 1_000_000, 0.95) == 0.0

    def test_known_quantile(self):
        # Losses (-returns) sorted; worst-case loss is 5% -> 50,000 on 1M.
        returns = [0.01, 0.02, -0.01, -0.02, -0.03, -0.04, -0.05, 0.0, 0.005, -0.005]
        var = pr.historical_var(returns, 1_000_000, 0.95)
        # 95th percentile of losses should land near the 5% loss.
        assert 40000.0 <= var <= 50000.0

    def test_all_gains_zero_var(self):
        var = pr.historical_var([0.01, 0.02, 0.03], 1_000_000, 0.95)
        assert var == 0.0


# --------------------------------------------------------------------------- #
# Wiring into IntelligenceService
# --------------------------------------------------------------------------- #
class TestIntelligenceContractRisk:
    def _svc(self):
        from unittest.mock import MagicMock

        return IntelligenceService(bedrock_client=MagicMock())

    def test_compute_contract_risk_fields(self):
        svc = self._svc()
        result = svc.compute_contract_risk(
            commodity="Copper",
            contract_price=8000.0,
            market_price=8500.0,
            volume=1000,
            volatility=0.02,
        )
        assert result["commodity"] == "Copper"
        assert result["mark_to_market_pnl"] == 500000.0  # (8500-8000)*1000
        assert result["position_value"] == 8_500_000.0
        # VaR = 8.5M * 0.02 * 1.645 = 279,650.
        assert result["value_at_risk"] == 279650.0
        assert result["conditional_var"] > result["value_at_risk"]
        assert result["stressed_var_crisis"] > result["value_at_risk"]
        assert 0.0 <= result["breach_probability"] <= 1.0

    def test_compute_contract_risk_loss(self):
        svc = self._svc()
        result = svc.compute_contract_risk(
            commodity="Nickel",
            contract_price=9000.0,
            market_price=8000.0,
            volume=500,
            volatility=0.03,
        )
        assert result["mark_to_market_pnl"] == -500000.0
