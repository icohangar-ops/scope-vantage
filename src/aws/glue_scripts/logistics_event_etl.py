# Glue ETL: Logistics Event Processing
# Ingests disruption/delay/bottleneck events and computes cost impact estimates.

import json
import logging
import os
import sys
from datetime import datetime

import boto3

sys.path.insert(0, "/opt/python")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Cost impact multipliers by severity
DAILY_COST_MULTIPLIERS = {
    "Low": 10000,
    "Medium": 50000,
    "High": 200000,
    "Critical": 1000000,
}


def process_logistics_events(event):
    """Process and persist logistics events, computing cost impact estimates.

    Expected event format:
    {
        "events": [
            {
                "event_type": "Disruption",
                "route": "Strait of Malacca",
                "origin": "China",
                "destination": "Europe",
                "carrier": "Maersk",
                "commodity": "Lithium Carbonate",
                "impact_severity": "High",
                "estimated_delay_days": 14,
                "description": "Port congestion causing delays"
            }
        ],
        "target_table": "logistics_events"
    }
    """
    events = event.get("events", [])

    database = os.environ.get("GLUE_DATABASE", "scope_vantage")
    athena = boto3.client("athena")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-vantage-queries/")

    results = []
    for evt in events:
        try:
            event_type = evt.get("event_type", "Shipment")
            severity = evt.get("impact_severity", "Low")
            delay_days = float(evt.get("estimated_delay_days", 0))
            daily_cost = DAILY_COST_MULTIPLIERS.get(severity, 10000)
            cost_impact = daily_cost * delay_days

            query = f"""
            INSERT INTO {database}.logistics_events
            VALUES (
                '{evt.get("event_id", f"EVT_{event_type}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")}',
                '{event_type}',
                '{evt.get("route", "")}',
                '{evt.get("origin", "")}',
                '{evt.get("destination", "")}',
                '{evt.get("carrier", "")}',
                '{evt.get("commodity", "")}',
                'Active',
                {delay_days},
                '{severity}',
                {cost_impact},
                '{evt.get("description", "")[:2000].replace("'", "''")}',
                TIMESTAMP '{datetime.utcnow().isoformat()}'
            )
            """

            response = athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}logistics/"},
            )
            results.append({
                "event_type": event_type,
                "severity": severity,
                "cost_impact": cost_impact,
                "query_id": response["QueryExecutionId"],
                "status": "submitted",
            })
            logger.info(f"Processed logistics event: {event_type} ({severity})")

        except Exception as e:
            logger.error(f"Error processing logistics event: {e}")
            results.append({"status": "error", "error": str(e)})

    # Compute aggregate disruption metrics
    try:
        agg_query = f"""
        INSERT INTO {database}.disruption_summary
        SELECT
            commodity,
            event_type,
            impact_severity,
            COUNT(*) AS event_count,
            SUM(estimated_delay_days) AS total_delay_days,
            SUM(cost_impact_estimate) AS total_cost_impact,
            CURRENT_TIMESTAMP AS computed_at
        FROM {database}.logistics_events
        WHERE status = 'Active'
        GROUP BY commodity, event_type, impact_severity
        """
        athena.start_query_execution(
            QueryString=agg_query,
            QueryExecutionContext={"Database": database},
            ResultConfiguration={"OutputLocation": f"{s3_output}logistics/summary/"},
        )
    except Exception as e:
        logger.error(f"Error computing disruption summary: {e}")

    return {
        "status": "completed",
        "events_processed": len(results),
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }


def lambda_handler(event, context):
    """AWS Lambda entry point for logistics event processing."""
    logger.info(f"Logistics event ETL triggered: {json.dumps(event)[:500]}")

    try:
        result = process_logistics_events(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
