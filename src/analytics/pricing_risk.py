"""
Quantitative pricing & risk analytics for commodity supply-chain contracts.

Ported from the (now-archivable) ``snowflake-commodity-supply-chain`` repo,
where these formulas lived as Snowpark Python UDFs and dbt macros. They are
re-implemented here in plain Python (stdlib ``math`` only, with an optional
NumPy fast path for the empirical estimators) so they are unit-testable and
runnable inside any AWS Lambda / Glue job without a Snowflake session.

Capabilities:
  * Black-Scholes pricing for commodity options embedded in contracts
  * Adjusted commodity pricing (quality / location / freight / FX factors)
  * Mark-to-market contract P&L
  * Parametric Value at Risk (VaR) and Conditional VaR / Expected Shortfall
  * Stress-tested VaR
  * Price-threshold breach probability

All functions are pure: no I/O, no global state.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence

# Standard normal z-scores for common one-tailed confidence levels.
_Z_SCORES = {
    0.90: 1.282,
    0.95: 1.645,
    0.99: 2.326,
    0.999: 3.090,
}

# Trading days per year, used to de-annualize volatility.
TRADING_DAYS = 252


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via the stdlib error function (no scipy needed)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _z_for_confidence(confidence_level: float) -> float:
    """Look up a z-score, defaulting to the 95% value for unknown levels."""
    return _Z_SCORES.get(confidence_level, _Z_SCORES[0.95])


def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    option_type: str = "CALL",
) -> float:
    """Black-Scholes price for a European commodity option.

    Args:
        spot: Current spot price of the underlying commodity.
        strike: Strike / exercise price.
        time_to_expiry: Time to expiry in years (> 0).
        risk_free_rate: Continuously-compounded risk-free rate (decimal).
        volatility: Annualized volatility (decimal, > 0).
        option_type: ``"CALL"`` or ``"PUT"``.

    Returns:
        Theoretical option price, rounded to 4 dp.

    Raises:
        ValueError: if time_to_expiry or volatility is not positive, or
            spot/strike are not positive, or option_type is unknown.
    """
    if time_to_expiry <= 0:
        raise ValueError("time_to_expiry must be positive")
    if volatility <= 0:
        raise ValueError("volatility must be positive")
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")

    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + volatility ** 2 / 2.0) * time_to_expiry
    ) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t

    discount = math.exp(-risk_free_rate * time_to_expiry)
    opt = option_type.upper()
    if opt == "CALL":
        price = spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
    elif opt == "PUT":
        price = strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
    else:
        raise ValueError("option_type must be 'CALL' or 'PUT'")
    return round(price, 4)


def calculate_commodity_price(
    base_price: float,
    quality_premium: float = 0.0,
    location_adjustment: float = 0.0,
    freight_surcharge: float = 0.0,
    currency_adj: float = 1.0,
) -> float:
    """Adjusted commodity price with premium / discount / freight / FX factors.

    Args:
        base_price: Base commodity price in USD.
        quality_premium: Quality premium/discount (decimal, e.g. 0.05 = +5%).
        location_adjustment: Location adjustment (decimal).
        freight_surcharge: Additional freight cost in USD per unit.
        currency_adj: Currency adjustment factor (default 1.0).

    Returns:
        Adjusted price, rounded to 4 dp.
    """
    adjusted = base_price * (1.0 + quality_premium) * (1.0 + location_adjustment)
    adjusted += freight_surcharge
    adjusted *= currency_adj
    return round(adjusted, 4)


def calculate_contract_pnl(
    contract_price: float, market_price: float, volume: float
) -> float:
    """Mark-to-market P&L for a contract position.

    Positive = unrealized gain, negative = unrealized loss.

    Args:
        contract_price: Original contracted price.
        market_price: Current market price.
        volume: Volume in applicable units.

    Returns:
        Mark-to-market P&L, rounded to 2 dp.
    """
    return round((market_price - contract_price) * volume, 2)


def calculate_var(
    position_value: float,
    volatility: float,
    confidence_level: float = 0.95,
    time_horizon: float = 1.0,
) -> float:
    """Parametric (variance-covariance) Value at Risk.

    Args:
        position_value: Total position value in USD.
        volatility: Per-period volatility (decimal).
        confidence_level: Confidence level (0.90 / 0.95 / 0.99 / 0.999).
        time_horizon: Holding period in periods (e.g. days). Scaled by sqrt(t).

    Returns:
        VaR estimate in USD (a non-negative loss magnitude), rounded to 2 dp.
    """
    z = _z_for_confidence(confidence_level)
    var = abs(position_value) * volatility * z * math.sqrt(time_horizon)
    return round(var, 2)


def calculate_cvar(
    position_value: float,
    volatility: float,
    confidence_level: float = 0.95,
) -> float:
    """Conditional VaR (Expected Shortfall): the closed-form normal estimate.

    For a normal distribution the expected shortfall at confidence ``c`` is
    ``sigma * pdf(z) / (1 - c)`` where ``z`` is the one-tailed z-score. This
    is the average loss *given* that the VaR threshold is breached, and is
    always >= the corresponding VaR.

    Args:
        position_value: Total position value in USD.
        volatility: Per-period volatility (decimal).
        confidence_level: Confidence level.

    Returns:
        CVaR / Expected Shortfall in USD, rounded to 2 dp.
    """
    z = _z_for_confidence(confidence_level)
    tail = 1.0 - confidence_level
    pdf_z = math.exp(-z * z / 2.0) / math.sqrt(2.0 * math.pi)
    es_multiplier = pdf_z / tail if tail > 0 else z
    cvar = abs(position_value) * volatility * es_multiplier
    return round(cvar, 2)


def stress_test_var(
    position_value: float, volatility: float, scenario_multiplier: float
) -> float:
    """Apply a stress-scenario multiplier to a base VaR-style exposure.

    Common multipliers: 1.5 (mild), 2.0 (moderate), 3.0 (severe), 5.0 (crisis).

    Args:
        position_value: Total position value in USD.
        volatility: Per-period volatility (decimal).
        scenario_multiplier: Stress severity multiplier.

    Returns:
        Stressed VaR estimate in USD, rounded to 2 dp.
    """
    return round(abs(position_value) * volatility * scenario_multiplier, 2)


def breach_probability(
    price_volatility: float, threshold_pct: float, time_days: float = 30.0
) -> float:
    """Two-tailed probability that price moves beyond +/- ``threshold_pct``.

    Models log-price as a driftless normal walk: de-annualizes volatility to a
    daily figure, scales to the horizon, and returns ``2 * (1 - CDF(z))`` — the
    probability of an absolute move exceeding the threshold in either direction.

    Args:
        price_volatility: Annualized price volatility (decimal).
        threshold_pct: Threshold as a percentage (e.g. 10.0 for 10%).
        time_days: Horizon in days.

    Returns:
        Probability of breach in [0.0, 1.0], rounded to 4 dp.
    """
    if price_volatility <= 0 or time_days <= 0:
        return 0.0
    daily_vol = price_volatility / math.sqrt(TRADING_DAYS)
    horizon_vol = daily_vol * math.sqrt(time_days)
    if horizon_vol == 0:
        return 0.0
    scaled_threshold = (threshold_pct / 100.0) / horizon_vol
    if scaled_threshold <= 0:
        return 1.0
    prob = 2.0 * (1.0 - _norm_cdf(scaled_threshold))
    return round(min(max(prob, 0.0), 1.0), 4)


def historical_var(
    returns: Sequence[float],
    position_value: float,
    confidence_level: float = 0.95,
) -> float:
    """Empirical (historical-simulation) VaR from a series of period returns.

    Uses the loss quantile of the supplied returns rather than a normal
    assumption. NumPy is used when available for the percentile; otherwise a
    pure-Python nearest-rank fallback is used.

    Args:
        returns: Historical per-period returns (decimal, e.g. -0.03 = -3%).
        position_value: Total position value in USD.
        confidence_level: Confidence level (e.g. 0.95).

    Returns:
        Historical VaR in USD (non-negative loss magnitude), rounded to 2 dp.
    """
    losses = sorted(-r for r in returns)  # losses are negated returns
    if not losses:
        return 0.0
    q = confidence_level
    try:
        import numpy as np  # optional fast path

        loss_q = float(np.percentile(np.asarray(losses, dtype=float), q * 100.0))
    except Exception:
        # Nearest-rank percentile fallback.
        rank = max(0, min(len(losses) - 1, int(math.ceil(q * len(losses))) - 1))
        loss_q = losses[rank]
    return round(abs(position_value) * max(loss_q, 0.0), 2)
