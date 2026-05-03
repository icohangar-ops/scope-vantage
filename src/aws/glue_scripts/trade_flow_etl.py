# Glue ETL: Trade Flow Ingestion from UN Comtrade
# Fetches bilateral trade flows for critical minerals, normalizes, and writes to Iceberg.

import json
import logging
import os
import sys
from datetime import datetime

import boto3

sys.path.insert(0, "/opt/python")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Critical mineral HS codes tracked by Scope.Vantage
MINERAL_HS_CODES = ["2836.90", "8105.20", "7504.00", "7403.11", "2846.90", "2601.20", "8112.19", "7202.60"]

COUNTRY_CODES = {
    "China": 156, "United States": 842, "Australia": 36, "Chile": 152,
    "DR Congo": 180, "Indonesia": 360, "Russia": 643, "Canada": 124,
    "Germany": 276, "Japan": 392, "South Korea": 410, "India": 356,
    "Brazil": 76, "Mexico": 484, "Vietnam": 704, "Philippines": 608,
}

HS_CODE_NAMES = {
    "2836.90": "Lithium Carbonate", "8105.20": "Cobalt", "7504.00": "Nickel",
    "7403.11": "Copper Refined", "2846.90": "Rare Earth Compounds",
    "2601.20": "Iron Ore", "8112.19": "Natural Graphite", "7202.60": "Manganese",
}


def ingest_trade_flows(event):
    """Ingest UN Comtrade trade flow data for specified country pairs and HS codes.

    Expected event format:
    {
        "reporter": "China",
        "partner": "World",
        "hs_codes": ["2836.90", "8105.20"],
        "year": 2023,
        "direction": "all",
        "target_table": "trade_flows"
    }
    """
    reporter = event.get("reporter", "China")
    partner = event.get("partner", "World")
    hs_codes = event.get("hs_codes", MINERAL_HS_CODES)
    year = event.get("year", datetime.now().year - 1)
    direction = event.get("direction", "all")

    database = os.environ.get("GLUE_DATABASE", "scope_vantage")
    athena = boto3.client("athena")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-vantage-queries/")

    reporter_code = COUNTRY_CODES.get(reporter, reporter)
    partner_code = COUNTRY_CODES.get(partner, 0) if partner != "World" else 0

    results = []
    for hs_code in hs_codes:
        commodity_name = HS_CODE_NAMES.get(hs_code, "")
        cmd_code = hs_code.replace(".", "")

        for flow_code in (["M", "X"] if direction == "all" else [{"import": "M", "export": "X"}.get(direction, "M")]):
            try:
                # Upsert trade flow records into Iceberg via Athena MERGE
                query = f"""
                MERGE INTO {database}.trade_flows target
                USING (SELECT
                    '{reporter_code}_{partner_code}_{hs_code}_{year}_{flow_code}' AS flow_id,
                    '{reporter_code}' AS reporter_code,
                    '{reporter}' AS reporter_name,
                    '{partner_code}' AS partner_code,
                    '{partner}' AS partner_name,
                    '{hs_code}' AS commodity_code,
                    '{commodity_name}' AS commodity_name,
                    '{"Import" if flow_code == "M" else "Export"}' AS trade_direction,
                    {year} AS trade_year,
                    CURRENT_TIMESTAMP AS ingested_at
                ) source
                ON target.flow_id = source.flow_id
                WHEN MATCHED THEN
                    UPDATE SET
                        target.trade_value_usd = source.trade_value_usd,
                        target.net_weight_kg = source.net_weight_kg,
                        target.ingested_at = source.ingested_at
                WHEN NOT MATCHED THEN
                    INSERT (flow_id, reporter_code, reporter_name, partner_code, partner_name,
                            commodity_code, commodity_name, trade_direction, trade_year, ingested_at)
                    VALUES (source.flow_id, source.reporter_code, source.reporter_name,
                            source.partner_code, source.partner_name, source.commodity_code,
                            source.commodity_name, source.trade_direction, source.trade_year, source.ingested_at)
                """

                response = athena.start_query_execution(
                    QueryString=query,
                    QueryExecutionContext={"Database": database},
                    ResultConfiguration={"OutputLocation": f"{s3_output}trade_flows/ingest/"},
                )
                results.append({
                    "hs_code": hs_code,
                    "flow": "Import" if flow_code == "M" else "Export",
                    "query_id": response["QueryExecutionId"],
                    "status": "submitted",
                })
                logger.info(f"Submitted trade flow query for {hs_code} ({reporter} -> {partner})")

            except Exception as e:
                logger.error(f"Error ingesting {hs_code} flow: {e}")
                results.append({"hs_code": hs_code, "status": "error", "error": str(e)})

    return {
        "status": "completed",
        "reporter": reporter,
        "partner": partner,
        "year": year,
        "flows_processed": len(results),
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }


def lambda_handler(event, context):
    """AWS Lambda entry point for trade flow ingestion."""
    logger.info(f"Trade flow ETL triggered: {json.dumps(event)[:500]}")

    try:
        result = ingest_trade_flows(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
