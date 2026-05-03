-- Athena View: Tariff Impact Analysis
-- Active tariffs with trade flow impact quantification

CREATE OR REPLACE VIEW scope_vantage.tariff_impact_v AS
SELECT
    tr.reg_id,
    tr.regulation_type,
    tr.imposing_country,
    tr.target_country,
    tr.commodity_code,
    tr.commodity_name,
    tr.rate_percent,
    tr.effective_date,
    tr.status,
    -- Join with actual trade flows to estimate impact
    COALESCE(tf.avg_annual_trade_value, 0) AS avg_annual_trade_value_usd,
    COALESCE(tf.avg_annual_trade_value, 0) * tr.rate_percent / 100.0 AS estimated_annual_tariff_cost,
    COALESCE(tf.trade_volume_tonnes, 0) AS avg_annual_volume_tonnes,
    tr.description,
    tr.created_at
FROM scope_vantage.tariff_regulations tr
LEFT JOIN (
    SELECT
        commodity_code,
        reporter_name AS partner_country,
        AVG(trade_value_usd) AS avg_annual_trade_value,
        AVG(net_weight_kg) / 1000.0 AS trade_volume_tonnes
    FROM scope_vantage.trade_flows
    WHERE trade_direction = 'Import'
    GROUP BY commodity_code, reporter_name
) tf ON tf.commodity_code = tr.commodity_code AND tf.partner_country = tr.target_country
WHERE tr.status IN ('Active', 'Proposed')
ORDER BY estimated_annual_tariff_cost DESC;
