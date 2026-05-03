"""
Intelligence Analysis Lambda Handler — computes composite risk scores and Bedrock AI briefings.

Orchestrated by Step Functions state machine:
1. Compute concentration risk scores from trade flow data
2. Call Bedrock for AI analysis via Converse API
3. Generate intelligence briefings and write to Iceberg
"""

import json
import logging
import os
from datetime import datetime

import boto3

logger = logging.getLogger(__name__)

SCORE_WEIGHTS = {"supply_risk": 0.30, "price_volatility": 0.25, "logistics_risk": 0.25, "policy_risk": 0.20}


def compute_composite_scores(event):
    """Compute composite supply chain risk scores for specified commodities.

    Expected event:
    {
        "commodities": ["Lithium Carbonate", "Cobalt", "Nickel"],
        "year": 2023
    }
    """
    commodities = event.get("commodities", [])
    year = event.get("year", datetime.now().year - 1)

    athena = boto3.client("athena")
    database = os.environ.get("GLUE_DATABASE", "scope_vantage")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-vantage-queries/")

    scores = []
    for commodity in commodities:
        try:
            query = f"""
            WITH trade_data AS (
                SELECT
                    tf.commodity_code,
                    tf.commodity_name,
                    tf.trade_value_usd,
                    tf.net_weight_kg
                FROM {database}.trade_flows tf
                WHERE tf.commodity_name = '{commodity}'
                  AND tf.trade_year = {year}
            ),
            conc AS (
                SELECT hhi_index, concentration_rating, country_count
                FROM {database}.concentration_metrics
                WHERE commodity_name = '{commodity}' AND trade_year = {year}
                LIMIT 1
            ),
            disruptions AS (
                SELECT COUNT(*) AS event_count, SUM(cost_impact_estimate) AS total_impact
                FROM {database}.logistics_events
                WHERE commodity = '{commodity}' AND status = 'Active'
            ),
            tariffs AS (
                SELECT AVG(rate_percent) AS avg_tariff
                FROM {database}.tariff_regulations
                WHERE commodity_name = '{commodity}' AND status = 'Active'
            )
            SELECT
                '{commodity}' AS commodity,
                COALESCE((SELECT hhi_index FROM conc), 0) AS hhi_index,
                COALESCE((SELECT concentration_rating FROM conc), 'Unknown') AS concentration_rating,
                COALESCE((SELECT event_count FROM disruptions), 0) AS active_disruptions,
                COALESCE((SELECT total_impact FROM disruptions), 0) AS disruption_cost,
                COALESCE((SELECT avg_tariff FROM tariffs), 0) AS avg_tariff_rate
            """

            response = athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}intelligence/scores/"},
            )
            scores.append({
                "commodity": commodity,
                "query_id": response["QueryExecutionId"],
                "status": "submitted",
            })
        except Exception as e:
            logger.error(f"Error computing score for {commodity}: {e}")
            scores.append({"commodity": commodity, "status": "error", "error": str(e)})

    return scores


def invoke_bedrock_analysis(commodity: str, score_data: dict) -> str:
    """Invoke Bedrock Converse API for supply chain intelligence analysis."""
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    prompt = f"""Analyze the supply chain intelligence for {commodity}:

Key Metrics:
- HHI Concentration Index: {score_data.get('hhi_index', 'N/A')}
- Concentration Rating: {score_data.get('concentration_rating', 'N/A')}
- Active Disruptions: {score_data.get('active_disruptions', 0)}
- Disruption Cost Impact: ${score_data.get('disruption_cost', 0):,.0f}
- Average Tariff Rate: {score_data.get('avg_tariff_rate', 0):.1f}%

Provide analysis covering:
1. Supply chain risks (concentration, geopolitical, logistics)
2. Price trend outlook and volatility factors
3. Trade policy impact assessment
4. Strategic recommendations for supply chain resilience"""

    try:
        response = bedrock.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=[{"text": "You are a senior supply chain intelligence analyst. Be data-driven and concise."}],
            inferenceConfig={"maxTokens": 1000, "temperature": 0.3},
        )
        content_blocks = response.get("output", {}).get("message", {}).get("content", [])
        return "".join(cb.get("text", "") for cb in content_blocks)
    except Exception as e:
        logger.error(f"Bedrock analysis failed for {commodity}: {e}")
        return f"Analysis unavailable: {str(e)}"


def write_briefings_to_iceberg(briefings: list):
    """Write intelligence briefings to Iceberg table via Athena."""
    athena = boto3.client("athena")
    database = os.environ.get("GLUE_DATABASE", "scope_vantage")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-vantage-queries/")

    for briefing in briefings:
        if briefing.get("status") != "analyzed":
            continue
        try:
            commodity = briefing["commodity"]
            summary = briefing.get("analysis", "")[:4000].replace("'", "''")
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            briefing_id = f"BRIEF_{commodity.replace(' ', '_')}_{ts}"

            query = f"""
            INSERT INTO {database}.intelligence_briefings
            VALUES (
                '{briefing_id}',
                TIMESTAMP '{datetime.utcnow().isoformat()}',
                'commodity',
                '{commodity}',
                '{summary}',
                '{briefing.get("risk_assessment", "Medium")}',
                '{json.dumps(briefing.get("opportunities", [])).replace("'", "''")}',
                '{json.dumps(briefing.get("recommendations", [])).replace("'", "''")}',
                {briefing.get("confidence_score", 0.5)},
                '{json.dumps(briefing.get("sources", [])).replace("'", "''")}'
            )
            """
            athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}briefings/write/"},
            )
        except Exception as e:
            logger.error(f"Error writing briefing for {commodity}: {e}")


def handler(event, context):
    """AWS Lambda entry point for intelligence analysis pipeline.

    Step Functions passes:
    {
        "step": "compute_scores" | "bedrock_analysis" | "write_briefings",
        "commodities": ["Lithium Carbonate", "Cobalt"],
        "scores": [...]  // for bedrock_analysis or write_briefings steps
    }
    """
    logger.info(f"Intelligence Lambda triggered: {json.dumps(event)[:500]}")

    step = event.get("step", "compute_scores")

    if step == "compute_scores":
        scores = compute_composite_scores(event)
        return {"statusCode": 200, "body": json.dumps({"step": step, "scores": scores})}

    elif step == "bedrock_analysis":
        scores = event.get("scores", [])
        for score in scores:
            commodity = score.get("commodity", "")
            analysis = invoke_bedrock_analysis(commodity, score)
            score["analysis"] = analysis
            score["status"] = "analyzed"
        return {"statusCode": 200, "body": json.dumps({"step": step, "scores": scores})}

    elif step == "write_briefings":
        write_briefings_to_iceberg(event.get("scores", []))
        return {"statusCode": 200, "body": json.dumps({"step": step, "status": "completed"})}

    return {"statusCode": 400, "body": json.dumps({"error": f"Unknown step: {step}"})}
