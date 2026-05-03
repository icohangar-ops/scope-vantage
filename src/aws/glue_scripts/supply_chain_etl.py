# Glue ETL: Supply Chain Node & Concentration Metrics
# Computes HHI indices, node risk scores, and supply chain concentration from trade flow data.

import json
import logging
import os
import sys
from datetime import datetime

import boto3

sys.path.insert(0, "/opt/python")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def compute_concentration_metrics(event):
    """Compute supply chain concentration metrics from trade flow data.

    Expected event format:
    {
        "commodity_codes": ["2836.90", "8105.20", "7504.00"],
        "year": 2023,
        "direction": "Import",
        "target_table": "supply_chain_nodes"
    }
    """
    commodity_codes = event.get("commodity_codes", ["2836.90", "8105.20", "7504.00"])
    year = event.get("year", datetime.now().year - 1)
    direction = event.get("direction", "Import")

    database = os.environ.get("GLUE_DATABASE", "scope_vantage")
    athena = boto3.client("athena")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-vantage-queries/")

    results = []
    for hs_code in commodity_codes:
        try:
            # Compute HHI for each commodity from trade flow data
            hhi_query = f"""
            WITH trade_shares AS (
                SELECT
                    partner_name,
                    SUM(trade_value_usd) AS total_value
                FROM {database}.trade_flows
                WHERE commodity_code = '{hs_code}'
                  AND trade_year = {year}
                  AND trade_direction = '{direction}'
                GROUP BY partner_name
            ),
            total AS (
                SELECT SUM(total_value) as grand_total FROM trade_shares
            ),
            shares AS (
                SELECT
                    ts.partner_name,
                    ts.total_value,
                    ts.total_value / t.grand_total AS market_share,
                    POWER(ts.total_value / t.grand_total, 2) AS hhi_contribution
                FROM trade_shares ts
                CROSS JOIN total t
            )
            SELECT
                '{hs_code}' AS commodity_code,
                '{direction}' AS trade_direction,
                {year} AS trade_year,
                COUNT(*) AS country_count,
                SUM(hhi_contribution) * 10000 AS hhi_index,
                CASE
                    WHEN SUM(hhi_contribution) * 10000 < 1500 THEN 'Unconcentrated'
                    WHEN SUM(hhi_contribution) * 10000 < 2500 THEN 'Moderately Concentrated'
                    ELSE 'Highly Concentrated'
                END AS concentration_rating,
                MAX(market_share) * 100 AS max_country_share_pct,
                CURRENT_TIMESTAMP AS computed_at
            FROM shares
            """

            response = athena.start_query_execution(
                QueryString=hhi_query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}concentration/"},
            )

            # Also compute top-5 country breakdown
            top5_query = f"""
            SELECT
                partner_name,
                SUM(trade_value_usd) AS total_trade_value,
                SUM(net_weight_kg) / 1000.0 AS total_weight_tonnes,
                CASE WHEN SUM(net_weight_kg) > 0
                    THEN SUM(trade_value_usd) / (SUM(net_weight_kg) / 1000.0)
                    ELSE 0 END AS unit_value_usd_per_tonne
            FROM {database}.trade_flows
            WHERE commodity_code = '{hs_code}'
              AND trade_year = {year}
              AND trade_direction = '{direction}'
            GROUP BY partner_name
            ORDER BY total_trade_value DESC
            LIMIT 5
            """

            athena.start_query_execution(
                QueryString=top5_query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}concentration/top5/"},
            )

            results.append({
                "commodity_code": hs_code,
                "hhi_query_id": response["QueryExecutionId"],
                "status": "submitted",
            })
            logger.info(f"Submitted concentration query for {hs_code}")

        except Exception as e:
            logger.error(f"Error computing concentration for {hs_code}: {e}")
            results.append({"commodity_code": hs_code, "status": "error", "error": str(e)})

    return {
        "status": "completed",
        "commodities_processed": len(results),
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }


def lambda_handler(event, context):
    """AWS Lambda entry point for supply chain concentration ETL."""
    logger.info(f"Supply chain ETL triggered: {json.dumps(event)[:500]}")

    try:
        result = compute_concentration_metrics(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
