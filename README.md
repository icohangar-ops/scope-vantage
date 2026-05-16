# Scope.Vantage — Supply Chain Intelligence Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-Native-orange.svg)](https://aws.amazon.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Overview

**Scope.Vantage** is a comprehensive supply chain intelligence platform built on AWS native services. It ingests global trade data from UN Comtrade, commodity prices from AlphaVantage and FRED, and uses Amazon Bedrock (Claude Haiku) to generate actionable intelligence briefings about supply chain risks, tariff impacts, and strategic opportunities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ UN Comtrade  │  │ AlphaVantage │  │  FRED Economic Data  │  │
│  │ (Trade Flows)│  │ (Commodities)│  │  (Macro Indicators)  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼─────────────────┼─────────────────────┼──────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS LAMBDA (INGESTION)                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  ingestion_handler.py — EventBridge Scheduled Trigger      │ │
│  │  - Fetches Comtrade trade flows for critical minerals      │ │
│  │  - Pulls commodity prices from AlphaVantage / FRED         │ │
│  │  - Writes raw data to S3 as Iceberg tables                 │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAKE (S3 + ICEBERG)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ trade_flows │  │ commodity    │  │ supply_chain           │ │
│  │ _raw        │  │ _prices      │  │ _risk_scores           │ │
│  ├─────────────┤  ├──────────────┤  ├────────────────────────┤ │
│  │ trade_flows │  │ logistics    │  │ intelligence           │ │
│  │ _cleaned    │  │ _events      │  │ _briefings             │ │
│  └─────────────┘  └──────────────┘  └────────────────────────┘ │
└─────────┬──────────────────┬──────────────────┬─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  AWS GLUE ETL PIPELINE                           │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│  │ trade_flow    │  │ commodity      │  │ supply_chain     │   │
│  │ _etl.py       │  │ _etl.py        │  │ _etl.py          │   │
│  │ - Clean raw   │  │ - Price trends │  │ - Risk scoring   │   │
│  │ - HS resolve  │  │ - Volatility   │  │ - Chain graphs   │   │
│  │ - Unit conv.  │  │ - Currency conv│  │ - Bottlenecks    │   │
│  └───────────────┘  └────────────────┘  └──────────────────┘   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP FUNCTIONS (ANALYSIS ORCHESTRATION)             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  1. Compute Risk Scores (SupplyChainService)               │ │
│  │  2. Analyze Tariff Impacts (TariffService)                 │ │
│  │  3. Generate AI Briefings (Bedrock Converse API)           │ │
│  │  4. Write Results to Iceberg Tables                        │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                 AMAZON ATHENA (QUERY ENGINE)                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ trade_analysis   │  │ commodity        │  │ supply_chain │  │
│  │ .sql             │  │ _pricing.sql     │  │ _risk.sql    │  │
│  │ - Top corridors  │  │ - Price compare  │  │ - Risk dash  │  │
│  │ - Volume trends  │  │ - Volatility     │  │ - HHI index  │  │
│  │ - YoY changes    │  │ - Trend analysis │  │ - Bottlenecks│  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│               INTELLIGENCE LAYER (BEDROCK AI)                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Claude 3 Haiku via Converse API                           │ │
│  │  - Composite Intelligence Scoring                          │ │
│  │  - Narrative Risk Analysis                                 │ │
│  │  - Strategic Recommendations                               │ │
│  │  - Cross-commodity Correlation Insights                    │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

- **Multi-Source Data Ingestion**: UN Comtrade (via `comtradeapicall`), AlphaVantage, FRED
- **Apache Iceberg Tables**: ACID-compliant table format on S3 with time-travel queries
- **Supply Chain Graph Mapping**: Origin → Processing → Manufacturing → End Market
- **Risk Scoring Engine**: Composite score (Supply 30% + Price Volatility 25% + Logistics 25% + Policy 20%)
- **AI-Powered Analysis**: Claude 3 Haiku generates narrative briefings via Bedrock Converse API
- **Tariff Impact Modeling**: Scenario analysis for trade policy changes
- **Concentration Risk**: Herfindahl-Hirschman Index (HHI) for geographic/supplier analysis
- **Athena Views**: Pre-built analytical views for trade, pricing, and risk dashboards

## Prerequisites

- Python 3.10+
- AWS account with Bedrock access enabled
- AWS credentials configured (via `.env` or IAM)
- Terraform 1.5+ (for infrastructure deployment)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your AWS credentials and API keys
```

### 3. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 4. Create Iceberg Tables

```bash
python notebooks/01_setup_iceberg_tables.py
```

### 5. Run the Full Pipeline

```bash
python notebooks/02_supply_chain_intelligence.py
```

### 6. Run Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
scope-vantage/
├── bedrock_client.py           # Bedrock Converse API wrapper
├── requirements.txt            # Python dependencies
├── src/
│   ├── models/                 # Domain models (6)
│   │   ├── trade_flow.py
│   │   ├── commodity.py
│   │   ├── supply_chain_node.py
│   │   ├── logistics_event.py
│   │   ├── tariff_regulation.py
│   │   └── intelligence_briefing.py
│   ├── services/               # Business logic (5)
│   │   ├── comtrade_service.py
│   │   ├── pricing_service.py
│   │   ├── supply_chain_service.py
│   │   ├── tariff_service.py
│   │   └── intelligence_service.py
│   ├── aws/                    # AWS integrations
│   │   ├── glue_scripts/       # ETL scripts (3)
│   │   └── athena_views/       # SQL views (3)
│   └── lambda/                 # Lambda handlers (2)
├── notebooks/                  # Setup & pipeline notebooks
├── terraform/                  # Infrastructure as Code
└── tests/                      # Test suite (50+ tests)
```

## API Usage

### ComtradeService — Trade Data Ingestion

```python
from src.services.comtrade_service import ComtradeService

svc = ComtradeService()
# Fetch lithium trade flows
flows = svc.fetch_trade_flows(
    reporter_code=842,  # Australia
    partner_code=156,   # China
    commodity_code="2836.90",  # Lithium carbonate
    year=2023,
)
```

### PricingService — Commodity Prices

```python
from src.services.pricing_service import PricingService

svc = PricingService()
prices = svc.get_commodity_price("LITHIUM")
trends = svc.get_price_trend("COPPER", window_days=90)
```

### IntelligenceService — AI Analysis

```python
from src.services.intelligence_service import IntelligenceService

svc = IntelligenceService()
briefing = svc.generate_briefing(
    scope="commodity",
    focus="Lithium",
    include_recommendations=True,
)
print(briefing.summary)
print(briefing.risk_assessment)
```

## Tracked Commodities (Critical Minerals)

| HS Code     | Commodity        | Category         |
|-------------|------------------|------------------|
| 2836.90     | Lithium Carbonate | Critical Mineral |
| 8105.20     | Cobalt           | Critical Mineral |
| 7504.00     | Nickel           | Critical Mineral |
| 7403.11     | Copper           | Critical Mineral |
| 2846.90     | Rare Earth       | Critical Mineral |

## Intelligence Scoring Formula

```
Composite Score = (
    Supply Risk (HHI-based)        × 0.30 +
    Price Volatility (30d σ/μ)     × 0.25 +
    Logistics Risk (events index)   × 0.25 +
    Policy Risk (tariff weight)     × 0.20
)
```

## AWS Cost Estimates (Monthly)

| Service         | Usage                          | Est. Cost   |
|-----------------|--------------------------------|-------------|
| S3 Storage      | 50 GB Iceberg tables           | ~$1.20      |
| Athena Queries  | 100 queries/month              | ~$5.00      |
| Lambda          | 10K invocations                | ~$0.50      |
| Step Functions  | 500 state transitions          | ~$0.75      |
| Glue ETL        | 3 jobs × 10 min                | ~$1.50      |
| Bedrock (Haiku) | 100K tokens/month              | ~$0.25      |
| EventBridge     | 30 scheduled rules             | ~$0.30      |
| **Total**       |                                | **~$9.50**  |

## License

MIT

---

## CHP Governance

This repository is hardened with the [Consensus Hardening Protocol (CHP)](https://codeberg.org/cubiczan/consensus-hardening-protocol), Cubiczan's decision-governance layer for multi-agent AI systems.

### Protocol Layers
- **R0 Gate**: All decisions must pass Solvable, Scoped, Valid, Worth_it checks
- **Foundation Disclosure**: 1-3 weakest assumptions, 1-2 invalidation conditions, 1 key vulnerability
- **Adversarial Layer**: Mandatory devil's advocate at Phase 0 and Round 3
- **State Machine**: EXPLORING → PROVISIONAL → PROVISIONAL_LOCK → LOCKED
- **Third-Party Validation**: Independent CONFIRM/REJECT before lock

### Domain Configuration
- **Category**: Mining / Supply Chain
- **Foundation Threshold**: 75
- **CFO Accuracy Guard**: Disabled

### Compliance Artifacts
| File | Purpose |
|------|---------|
| `.chp/STATE_MACHINE.md` | Decision state transitions |
| `.chp/R0_CONFIG.yaml` | Domain-calibrated thresholds |
| `.chp/ADVERSARIAL_PROMPTS.md` | Standardized challenge templates |
| `.chp/CHP_COMPLIANCE.md` | Compliance tracking & audit trail |

### CHP Version
cognitive-mesh-orchestrator 0.1.0 | [Protocol Docs](https://codeberg.org/cubiczan/consensus-hardening-protocol)

