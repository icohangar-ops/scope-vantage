-- Athena View: Supply Chain Risk Dashboard
-- HHI concentration, node risk scores, and commodity-level risk summaries

CREATE OR REPLACE VIEW scope_vantage.supply_chain_risk_v AS
SELECT
    cc.commodity_code,
    cc.commodity_name,
    cc.trade_direction,
    cc.trade_year,
    cc.country_count,
    cc.hhi_index,
    cc.concentration_rating,
    cc.max_country_share_pct,
    -- Risk score derived from concentration
    CASE
        WHEN cc.hhi_index >= 2500 THEN 80 + (cc.hhi_index - 2500) / 100.0 * 4
        WHEN cc.hhi_index >= 1500 THEN 50 + (cc.hhi_index - 1500) / 100.0 * 10
        ELSE 20 + cc.hhi_index / 75.0
    END AS concentration_risk_score,
    -- Count active logistics disruptions for this commodity
    COALESCE(le.active_disruptions, 0) AS active_disruptions,
    COALESCE(le.total_cost_impact, 0) AS disruption_cost_impact_usd,
    -- Active tariffs
    COALESCE(tr.active_tariff_count, 0) AS active_tariff_count,
    COALESCE(tr.max_tariff_rate, 0) AS max_applicable_tariff_pct,
    cc.computed_at
FROM scope_vantage.concentration_metrics cc
LEFT JOIN (
    SELECT commodity, COUNT(*) AS active_disruptions, SUM(cost_impact_estimate) AS total_cost_impact
    FROM scope_vantage.logistics_events WHERE status = 'Active' GROUP BY commodity
) le ON le.commodity = cc.commodity_name
LEFT JOIN (
    SELECT commodity_code, COUNT(*) AS active_tariff_count, MAX(rate_percent) AS max_tariff_rate
    FROM scope_vantage.tariff_regulations WHERE status = 'Active' AND regulation_type = 'Tariff'
    GROUP BY commodity_code
) tr ON tr.commodity_code = cc.commodity_code
ORDER BY cc.hhi_index DESC;
