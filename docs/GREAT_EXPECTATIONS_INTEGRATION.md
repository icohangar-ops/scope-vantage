# Great Expectations Data Quality Validation for Scope Vantage

## Overview

[Great Expectations](https://greatexpectations.io/) (12K+ GitHub stars) is a Python-based data quality framework that validates, profiles, and documents data. It defines "expectations" about your data — assertions on columns, rows, or entire tables — and surfaces quality issues before they enter your analytics pipeline.

This integration adds expectation suites to Scope Vantage's supply chain intelligence platform, validating trade data, commodity prices, and logistics events at the ingestion boundary. Combined with the `PolarsDataProcessor`, it ensures that every dataset feeding risk scoring, tariff analysis, and AI briefings meets quality standards.

---

## Why Great Expectations for Scope Vantage?

Scope Vantage ingests data from UN Comtrade, AlphaVantage, and FRED into Iceberg tables on S3. Bad data — invalid commodity codes, negative trade values, malformed country codes — corrupts supply chain risk scores and intelligence briefings. GX validates data at the source, before PolarsDataProcessor ever touches it.

| GX Feature | Scope Vantage Use Case |
|------------|------------------------|
| **Expectation Suites** | Declarative validation rules for trade_data, commodity_prices, logistics_events |
| **Pandas/Polars Integration** | Validate DataFrames in-memory before writing to Iceberg |
| **S3 Checkpoint Storage** | Store validation results alongside Iceberg tables |
| **Data Docs** | Auto-generated docs describing expected data shape |
| **Custom Expectations** | Validate HS6 commodity codes, ISO country codes, positive trade values |
| **Lightweight CLI** | Run validation in Lambda or Glue ETL scripts |

---

## Installation

### 1. Install Great Expectations

```bash
pip install great_expectations
# Already in requirements.txt for scope-vantage
```

### 2. Initialize GX

```bash
cd scope-vantage
great_expectations init
```

### 3. Configure the project

Edit `great_expectations/great_expectations.yml`:

```yaml
config_version: 3.0
datasources:
  local_pandas:
    class_name: Datasource
    execution_engine:
      class_name: PandasExecutionEngine
    data_connectors:
      default_runtime_data_connector:
        class_name: RuntimeDataConnector
        batch_identifiers:
          - default_identifier_name
      default_inferred_data_connector:
        class_name: InferredAssetFilesystemDataConnector
        name: whole_table
        base_directory: data/
        glob_directive: "*.parquet"
```

---

## Expectation Suites

### 1. Trade Data (`trade_data`)

Validates UN Comtrade trade flow data in `trade_flows_raw` and `trade_flows_cleaned` Iceberg tables.

```json
{
  "expectation_suite_name": "trade_data_suite",
  "expectations": [
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "flow_id" }
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "reporter_code" }
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "partner_code" }
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "commodity_code" }
    },
    {
      "expectation_type": "expect_column_values_to_match_regex",
      "kwargs": {
        "column": "commodity_code",
        "regex": "^\\d{4}\\.\\d{2}$"
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_in_set",
      "kwargs": {
        "column": "trade_direction",
        "value_set": ["Import", "Export"]
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_between",
      "kwargs": {
        "column": "trade_value_usd",
        "min_value": 0.0,
        "max_value": 100000000000
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_between",
      "kwargs": {
        "column": "net_weight_kg",
        "min_value": 0.0,
        "max_value": 10000000000
      }
    },
    {
      "expectation_type": "expect_column_values_to_match_regex",
      "kwargs": {
        "column": "reporter_code",
        "regex": "^\\d{1,3}$"
      }
    },
    {
      "expectation_type": "expect_column_values_to_match_regex",
      "kwargs": {
        "column": "partner_code",
        "regex": "^\\d{1,3}$"
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_in_set",
      "kwargs": {
        "column": "commodity_code",
        "value_set": [
          "2836.90", "8105.20", "7504.00", "7403.11", "2846.90",
          "2601.20", "2616.10", "7202.60", "8104.20", "8112.19"
        ]
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_unique",
      "kwargs": { "column": "flow_id" }
    },
    {
      "expectation_type": "expect_column_values_to_be_between",
      "kwargs": {
        "column": "year",
        "min_value": 2000,
        "max_value": 2030
      }
    },
    {
      "expectation_type": "expect_table_row_count_to_be_between",
      "kwargs": {
        "min_value": 10,
        "max_value": 10000000
      }
    }
  ]
}
```

**Key validations:**
- `commodity_code` must match HS6 format (`NNNN.NN`) and be one of the tracked critical minerals
- `trade_value_usd` must be positive (negative values indicate data errors)
- `reporter_code` and `partner_code` must be valid ISO 3166 numeric country codes
- `trade_direction` must be Import or Export
- `flow_id` must be unique (no duplicate ingestion)

### 2. Commodity Prices (`commodity_prices`)

Validates AlphaVantage and FRED commodity price data.

```json
{
  "expectation_suite_name": "commodity_prices_suite",
  "expectations": [
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "commodity" }
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "price" }
    },
    {
      "expectation_type": "expect_column_values_to_be_between",
      "kwargs": {
        "column": "price",
        "min_value": 0.01,
        "max_value": 1000000
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_in_set",
      "kwargs": {
        "column": "commodity",
        "value_set": [
          "LITHIUM", "COBALT", "NICKEL", "COPPER", "RARE_EARTH",
          "IRON_ORE", "SILVER", "MANGANESE", "MAGNESIUM", "GRAPHITE"
        ]
      }
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "date" }
    },
    {
      "expectation_type": "expect_column_values_to_match_regex",
      "kwargs": {
        "column": "date",
        "regex": "^\\d{4}-\\d{2}-\\d{2}$"
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_in_set",
      "kwargs": {
        "column": "source",
        "value_set": ["AlphaVantage", "FRED"]
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_between",
      "kwargs": {
        "column": "date",
        "min_value": "2015-01-01",
        "max_value": "2030-12-31"
      }
    }
  ]
}
```

**Key validations:**
- `commodity` must be one of the tracked commodities
- `price` must be positive (commodity prices cannot be zero or negative)
- `date` must be in ISO format and within a valid range
- `source` must be AlphaVantage or FRED (known data providers)

### 3. Logistics Events (`logistics_events`)

Validates shipping, port, and supply chain disruption events.

```json
{
  "expectation_suite_name": "logistics_events_suite",
  "expectations": [
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "event_id" }
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "event_type" }
    },
    {
      "expectation_type": "expect_column_values_to_be_in_set",
      "kwargs": {
        "column": "event_type",
        "value_set": [
          "port_congestion", "shipping_delay", "tariff_change",
          "sanction", "natural_disaster", "labor_strike", "capacity_reduction"
        ]
      }
    },
    {
      "expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": { "column": "event_date" }
    },
    {
      "expectation_type": "expect_column_values_to_be_between",
      "kwargs": {
        "column": "severity_score",
        "min_value": 1,
        "max_value": 10
      }
    },
    {
      "expectation_type": "expect_column_values_to_be_unique",
      "kwargs": { "column": "event_id" }
    }
  ]
}
```

---

## Integration with PolarsDataProcessor

GX validates DataFrames before they enter the `PolarsDataProcessor` pipeline. This catches quality issues at the boundary — before filtering, aggregation, or risk scoring.

### Validation Before Processing

```python
import great_expectations as gx
import polars as pl
from src.polars_utils import PolarsDataProcessor

def validate_and_process_trade_data(df: pl.DataFrame) -> PolarsDataProcessor:
    """Validate trade data with GX, then process with Polars."""
    context = gx.get_context()

    # Convert Polars DataFrame to Pandas for GX (GX works with Pandas natively)
    pandas_df = df.to_pandas()

    # Create a batch request from the DataFrame
    batch_request = context.sources.add_pandas(name="trade_data_source").get_batch_request(
        dataframe=pandas_df,
    )

    # Load the expectation suite
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name="trade_data_suite",
    )

    result = validator.validate()

    if not result.success:
        failed = [r for r in result.results if not r.success]
        raise ValueError(
            f"Trade data validation failed: {len(failed)} expectations failed. "
            f"Failed: {[r.expectation_config.expectation_type for r in failed]}"
        )

    return PolarsDataProcessor(df)
```

### Batch Validation Pipeline

```python
import great_expectations as gx
import polars as pl
from src.polars_utils import PolarsDataProcessor

SUITES = {
    "trade_data": "trade_data_suite",
    "commodity_prices": "commodity_prices_suite",
    "logistics_events": "logistics_events_suite",
}

def validate_and_process(df: pl.DataFrame, dataset_name: str) -> PolarsDataProcessor:
    """Validate a Polars DataFrame with GX, then wrap in PolarsDataProcessor."""
    context = gx.get_context()
    pandas_df = df.to_pandas()

    batch_request = context.sources.add_pandas(name=f"{dataset_name}_source").get_batch_request(
        dataframe=pandas_df,
    )

    suite_name = SUITES[dataset_name]
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=suite_name,
    )

    result = validator.validate()

    if not result.success:
        failed_expectations = [
            r.expectation_config for r in result.results if not r.success
        ]
        raise ValueError(f"Validation failed for {dataset_name}: {failed_expectations}")

    return PolarsDataProcessor(df)
```

---

## Iceberg Tables on S3

### Validating Iceberg Table Data

GX can validate data written to Iceberg tables on S3 by reading them into Pandas/Polars DataFrames.

```python
import great_expectations as gx
import pyarrow.iceberg as iceberg

# Read Iceberg table into Pandas
table = iceberg.table("s3://scope-vantage-lake/trade_flows_raw")
df = table.scan().to_pandas()

# Validate with GX
context = gx.get_context()
batch_request = context.sources.add_pandas(name="iceberg_trade_data").get_batch_request(
    dataframe=df,
)

validator = context.get_validator(
    batch_request=batch_request,
    expectation_suite_name="trade_data_suite",
)

result = validator.validate()
print(f"Iceberg validation: {'PASSED' if result.success else 'FAILED'}")
```

### Storing Checkpoints on S3

GX can persist validation results to S3, alongside your Iceberg tables:

```yaml
# great_expectations/great_expectations.yml
stores:
  checkpoint_store:
    class_name: ExpectationsStore
    store_backend:
      class_name: TupleS3StoreBackend
      bucket: scope-vantage-gx-store
      prefix: checkpoints/

  validations_store:
    class_name: ValidationsStore
    store_backend:
      class_name: TupleS3StoreBackend
      bucket: scope-vantage-gx-store
      prefix: validations/
```

---

## Running Expectations in the Pipeline

### Option 1: In Lambda Ingestion

```python
# src/lambda/ingestion_handler.py
import great_expectations as gx

def lambda_handler(event, context):
    # Fetch data from UN Comtrade
    raw_data = fetch_comtrade_data(event)

    # Validate before writing to Iceberg
    pandas_df = raw_data.to_pandas()
    batch_request = context.sources.add_pandas(name="comtrade").get_batch_request(
        dataframe=pandas_df,
    )
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name="trade_data_suite",
    )
    result = validator.validate()

    if not result.success:
        # Log failed expectations, alert, or skip write
        raise ValueError("Trade data quality check failed")

    # Write validated data to Iceberg
    write_to_iceberg(raw_data, "s3://scope-vantage-lake/trade_flows_raw")
```

### Option 2: Glue ETL Validation

```python
# src/aws/glue_scripts/trade_flow_etl.py
import great_expectations as gx
import polars as pl
from src.polars_utils import PolarsDataProcessor

def validate_trade_flows(input_path: str, output_path: str):
    """Validate and transform trade flow data."""
    df = pl.read_parquet(input_path)

    # Convert to Pandas for GX
    pandas_df = df.to_pandas()

    context = gx.get_context()
    batch_request = context.sources.add_pandas(name="glue_trade").get_batch_request(
        dataframe=pandas_df,
    )
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name="trade_data_suite",
    )
    result = validator.validate()

    if not result.success:
        raise ValueError("Trade flow validation failed in Glue ETL")

    # Process with PolarsDataProcessor
    processor = PolarsDataProcessor(df)
    cleaned = processor.filter_by_commodity("LITHIUM")  # example

    cleaned.df.write_parquet(output_path)
```

### Option 3: Scheduled Checkpoint

```bash
# Run validation as a scheduled task
great_expectations checkpoint run trade_data_validation

# Or validate all suites
python scripts/run_gx_validation.py
```

---

## Integration with the Scope Vantage Pipeline

```
UN Comtrade / AlphaVantage / FRED
    ↓
Lambda Ingestion (fetch raw data)
    ↓
Great Expectations validation (expectation suites)
    ↓ (must pass)
Write to Iceberg Tables on S3
    ↓
Glue ETL (clean, transform, unit conversion)
    ↓
PolarsDataProcessor (filter, aggregate, volatility analysis)
    ↓
Risk Scoring Engine (composite score, HHI index)
    ↓
Intelligence Briefings (Claude 3 Haiku via Bedrock)
```

### Pipeline Integration Pattern

```yaml
# In your Lambda or Step Function definition
steps:
  - name: Fetch data
    run: fetch_from_comtrade()

  - name: Validate data
    run: python scripts/run_gx_validation.py
    description: "Run GX expectation suites before Iceberg write"

  - name: Write to Iceberg
    run: write_to_iceberg()

  - name: Process with Polars
    run: python -c "from src.polars_utils import PolarsDataProcessor; ..."
```

---

## GX + PolarsDataProcessor: Validation Flow

```
┌─────────────────────────────────────────────────────┐
│                  DATA SOURCE                         │
│  UN Comtrade / AlphaVantage / FRED / S3 Iceberg     │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│           GREAT EXPECTATIONS VALIDATION              │
│  ┌───────────────────────────────────────────────┐  │
│  │  1. Load expectation suite (trade_data, etc.) │  │
│  │  2. Convert Polars → Pandas (for GX)          │  │
│  │  3. Run validation                            │  │
│  │  4. If failed → raise / alert / skip          │  │
│  │  5. If passed → continue to processing        │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│           POLARS DATA PROCESSOR                      │
│  ┌───────────────────────────────────────────────┐  │
│  │  filter_by_commodity()                        │  │
│  │  filter_by_country()                          │  │
│  │  filter_by_date_range()                       │  │
│  │  aggregate_by_region()                        │  │
│  │  rolling_stats()                              │  │
│  │  compute_volatility()                         │  │
│  │  hhi_index()                                  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│         RISK SCORING & INTELLIGENCE                  │
│  Composite Score = Supply 30% + Price 25%           │
│                   + Logistics 25% + Policy 20%       │
└─────────────────────────────────────────────────────┘
```

---

## References

- [Great Expectations Documentation](https://docs.greatexpectations.io/)
- [GX Pandas Integration](https://docs.greatexpectations.io/docs/reference/integrations/datasource-framework/pandas)
- [GX S3 Store Backend](https://docs.greatexpectations.io/docs/reference/stores_and_batch_requests)
- [Apache Iceberg Python API](https://iceberg.apache.org/docs/latest/python-api/)
- [Polars DataFrames](https://pola-rs.github.io/polars/)
