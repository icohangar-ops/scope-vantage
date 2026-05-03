"""
Comtrade Ingestion Lambda Handler — Fetches trade data via comtradeapicall and writes to S3.

Triggered by EventBridge schedule or Step Functions.
Uses comtradeapicall library to fetch UN Comtrade data for critical minerals.
"""

import json
import logging
import os
from datetime import datetime

import boto3

logger = logging.getLogger(__name__)

MINERAL_HS_CODES = ["2836.90", "8105.20", "7504.00", "7403.11", "2846.90", "2601.20", "8112.19", "7202.60"]

COUNTRY_CODES = {
    "China": 156, "United States": 842, "Australia": 36, "Chile": 152,
    "DR Congo": 180, "Indonesia": 360, "Russia": 643, "Canada": 124,
    "Germany": 276, "Japan": 392, "South Korea": 410, "India": 356,
}

HS_CODE_NAMES = {
    "2836.90": "Lithium Carbonate", "8105.20": "Cobalt", "7504.00": "Nickel",
    "7403.11": "Copper Refined", "2846.90": "Rare Earth Compounds",
    "2601.20": "Iron Ore", "8112.19": "Natural Graphite", "7202.60": "Manganese",
}


def fetch_comtrade_data(event):
    """Fetch UN Comtrade data for specified parameters.

    Expected event:
    {
        "reporter": "China",
        "partner": "World",
        "hs_codes": ["2836.90", "8105.20"],
        "year": 2023,
        "direction": "all"
    }
    """
    reporter = event.get("reporter", "China")
    partner = event.get("partner", "World")
    hs_codes = event.get("hs_codes", MINERAL_HS_CODES)
    year = event.get("year", datetime.now().year - 1)
    direction = event.get("direction", "all")

    reporter_code = COUNTRY_CODES.get(reporter, reporter)
    partner_code = COUNTRY_CODES.get(partner, 0) if partner != "World" else 0

    s3 = boto3.client("s3")
    bucket = os.environ.get("RAW_BUCKET", "scope-vantage-raw")
    prefix = f"comtrade/{reporter}/{partner}/{year}/"

    records = []
    try:
        import comtradeapicall as ct

        subscription_key = os.environ.get("UN_COMTRADE_KEY", "")
        if subscription_key:
            ct.subscribeComtradeApi(subscription_key)

        flow_codes = ["M", "X"] if direction == "all" else [{"import": "M", "export": "X"}.get(direction, "M")]

        for hs_code in hs_codes:
            cmd_code = hs_code.replace(".", "")
            commodity_name = HS_CODE_NAMES.get(hs_code, "")

            for flow_code in flow_codes:
                try:
                    data = ct.getFinalData(
                        reporterCode=reporter_code,
                        partnerCode=partner_code,
                        freq="A", clCode="HS", cmdCode=cmd_code,
                        flowCode=flow_code, period=str(year),
                    )
                    if data is not None and not data.empty:
                        for _, row in data.iterrows():
                            record = {
                                "reporter_code": str(getattr(row, "reporterCode", "")),
                                "partner_code": str(getattr(row, "partnerCode", "")),
                                "commodity_code": hs_code,
                                "commodity_name": commodity_name,
                                "trade_direction": "Import" if flow_code == "M" else "Export",
                                "year": year,
                                "net_weight_kg": float(getattr(row, "netWeightKg", 0) or 0),
                                "trade_value_usd": float(getattr(row, "tradeValue", 0) or 0),
                                "ingested_at": datetime.utcnow().isoformat(),
                            }
                            records.append(record)
                except Exception as e:
                    logger.warning(f"Comtrade fetch failed for {hs_code}/{flow_code}: {e}")

        # Write to S3 as JSON Lines
        if records:
            key = f"{prefix}trade_flows.jsonl"
            body = "\n".join(json.dumps(r) for r in records)
            s3.put_object(Bucket=bucket, Key=key, Body=body)
            logger.info(f"Wrote {len(records)} records to s3://{bucket}/{key}")

    except ImportError:
        logger.error("comtradeapicall not installed in Lambda environment")
        return {"status": "error", "error": "comtradeapicall not installed"}

    return {
        "status": "completed",
        "reporter": reporter,
        "partner": partner,
        "year": year,
        "records_fetched": len(records),
        "s3_path": f"s3://{bucket}/{prefix}" if records else "",
        "timestamp": datetime.utcnow().isoformat(),
    }


def handler(event, context):
    """AWS Lambda entry point for Comtrade data ingestion."""
    logger.info(f"Comtrade ingestion triggered: {json.dumps(event)[:500]}")

    try:
        result = fetch_comtrade_data(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
