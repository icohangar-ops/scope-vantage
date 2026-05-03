-- Athena View: Critical Mineral Trade Flows
-- Bilateral trade flow analysis with unit value and concentration metrics

CREATE OR REPLACE VIEW scope_vantage.critical_mineral_flows_v AS
SELECT
    tf.flow_id,
    tf.reporter_name,
    tf.partner_name,
    tf.commodity_code,
    tf.commodity_name,
    tf.trade_direction,
    tf.trade_year,
    tf.net_weight_kg,
    tf.net_weight_kg / 1000.0 AS net_weight_tonnes,
    tf.trade_value_usd,
    CASE WHEN tf.net_weight_kg > 0
        THEN tf.trade_value_usd / tf.net_weight_kg
        ELSE NULL
    END AS unit_value_usd_per_kg,
    CASE WHEN tf.net_weight_kg > 0
        THEN tf.trade_value_usd / (tf.net_weight_kg / 1000.0)
        ELSE NULL
    END AS unit_value_usd_per_tonne,
    tf.ingested_at
FROM scope_vantage.trade_flows tf
WHERE tf.commodity_code IN ('2836.90', '8105.20', '7504.00', '7403.11', '2846.90', '2601.20', '8112.19', '7202.60')
ORDER BY tf.trade_year DESC, tf.trade_value_usd DESC;
