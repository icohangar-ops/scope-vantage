# Airbyte Agents Integration — Scope.Vantage

This document describes how [Airbyte Agents](https://docs.airbyte.com/ai-agents) can replace the custom Lambda ingestion layer for UN Comtrade, AlphaVantage, and FRED data with managed connectors, removing ~800 lines of custom Python and adding incremental syncs, schema management, and error recovery.

---

## Overview

Scope.Vantage currently ingests data via Lambda handlers that call REST APIs directly. Airbyte Agents can replace these with declarative source configurations.

**Integration options:**
- **[MCP](https://docs.airbyte.com/ai-agents/interfaces/mcp)** — Remote MCP server. Best for ad-hoc queries via Claude/Cursor.
- **[SDK](https://docs.airbyte.com/ai-agents/interfaces/sdk)** — Python library. Best for replacing Lambda-based ingestion.
- **[API](https://docs.airbyte.com/ai-agents/interfaces/sdk)** — REST for infrastructure-as-code orchestration.

---

## Integration Points

### 1. Replace Lambda Ingestion with Airbyte Sources

| Current Service | File | Data | Airbyte Alternative |
|----------------|------|------|-------------------|
| `ComtradeService` + `comtrade_ingestion_handler` Lambda | `src/services/comtrade_service.py`, `src/lambda/comtrade_ingestion_handler.py` | UN Comtrade trade flows | Airbyte UN Comtrade (or generic HTTP) source |
| `PricingService` (in-process) | `src/services/pricing_service.py` | AlphaVantage commodity prices | Airbyte AlphaVantage source |
| `PricingService` (FRED) | `src/services/pricing_service.py` | FRED macro indicators | Airbyte FRED source |

### 2. Airbyte → Iceberg Pipeline

```
External Sources
  ├── UN Comtrade ──→ Airbyte Source ──→ S3 ──→ Iceberg Table: trade_flows
  ├── AlphaVantage ──→ Airbyte Source ──→ S3 ──→ Iceberg Table: commodity_prices
  ├── FRED ──────────→ Airbyte Source ──→ S3 ──→ Iceberg Table: macro_indicators
  └── Tariff APIs ───→ Airbyte Source ──→ S3 ──→ Iceberg Table: tariff_regulations
                                                  │
                                                  ▼
                                          Glue ETL (unchanged)
                                          Athena Views (unchanged)
                                          Bedrock AI (unchanged)
```

### 3. Example SDK Usage

```python
from airbyte_agent_sdk import connect

async def refresh_trade_data():
    """Replace the Comtrade ingestion Lambda."""
    comtrade = connect("un-comtrade")  # or custom HTTP connector
    try:
        result = await comtrade.execute("trade_flows", "list", params={
            "freq": "M",
            "cmdCode": "26",  # ores, slag and ash
            "period": "202601",
            "fmt": "json",
        })
        # Write to Iceberg-compatible destination
        print(f"Synced {len(result.data)} trade records")
    finally:
        await comtrade.close()
```

### 4. Remaining Analysis Pipeline (Unchanged)

The Glue ETL scripts, Step Functions orchestrator, Athena views, and Bedrock AI analysis run on the same Iceberg tables, regardless of how data arrived.

---

## Getting Started

1. **Sign up** at [app.airbyte.ai](https://app.airbyte.ai).
2. **Install the SDK**:
   ```bash
   uv add airbyte-agent-sdk
   ```
3. **Add to `.env.example`**:
   ```
   AIRBYTE_CLIENT_ID=your_client_id
   AIRBYTE_CLIENT_SECRET=***   ```
4. **Create Airbyte sync configurations** for each source, replacing the EventBridge → Lambda triggers.

---

## Connector Catalog

| Category | Connectors | Scope.Vantage Use |
|----------|-----------|------------------|
| **Trade Data** | UN Comtrade (custom), WTO Tariff | Trade flows, tariff regulations |
| **Financial** | AlphaVantage, FRED, Yahoo Finance | Commodity prices, macro indicators |
| **Logistics** | Generic HTTP / FourKites | Supply chain disruption events |
| **Geopolitical** | World Bank, OFAC sanctions | Country risk, policy changes |
| **Data Warehouse** | Snowflake, BigQuery, S3, Iceberg | Storage layer |

Full catalog: [docs.airbyte.com/ai-agents/connectors](https://docs.airbyte.com/ai-agents/connectors)
