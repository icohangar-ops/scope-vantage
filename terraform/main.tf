# Scope.Vantage AWS Infrastructure
# S3 + Iceberg + Glue + Athena + Lambda + Step Functions + EventBridge

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ============================================================
# S3 Buckets
# ============================================================

resource "aws_s3_bucket" "raw" {
  bucket = "${var.project_name}-raw-${var.environment}"

  lifecycle_rule {
    id      = "transition-to-ia"
    enabled = true
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }
}

resource "aws_s3_bucket" "iceberg_warehouse" {
  bucket = "${var.project_name}-warehouse-${var.environment}"
}

resource "aws_s3_bucket" "athena_output" {
  bucket = "${var.project_name}-queries-${var.environment}"

  lifecycle_rule {
    id      = "cleanup"
    enabled = true
    expiration {
      days = 30
    }
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = toset([aws_s3_bucket.raw.id, aws_s3_bucket.iceberg_warehouse.id, aws_s3_bucket.athena_output.id])

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ============================================================
# Glue Database & Tables
# ============================================================

resource "aws_glue_catalog_database" "vantage" {
  name = var.glue_database
}

resource "aws_glue_catalog_table" "trade_flows" {
  name          = "trade_flows"
  database_name = aws_glue_catalog_database.vantage.name

  table_type = "ICEBERG"
  parameters = {
    "table_type"           = "ICEBERG"
    "format_version"       = "2"
    "metadata_compression" = "gzip"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.iceberg_warehouse.bucket}/trade_flows/"
    input_format  = "org.apache.hadoop.mapred.FileInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "flow_id"
      type = "string"
    }
    columns {
      name = "reporter_code"
      type = "string"
    }
    columns {
      name = "reporter_name"
      type = "string"
    }
    columns {
      name = "partner_code"
      type = "string"
    }
    columns {
      name = "partner_name"
      type = "string"
    }
    columns {
      name = "commodity_code"
      type = "string"
    }
    columns {
      name = "commodity_name"
      type = "string"
    }
    columns {
      name = "trade_direction"
      type = "string"
    }
    columns {
      name = "trade_year"
      type = "int"
    }
    columns {
      name = "net_weight_kg"
      type = "double"
    }
    columns {
      name = "trade_value_usd"
      type = "double"
    }
    columns {
      name = "ingested_at"
      type = "timestamp"
    }
  }
}

resource "aws_glue_catalog_table" "logistics_events" {
  name          = "logistics_events"
  database_name = aws_glue_catalog_database.vantage.name

  table_type = "ICEBERG"
  parameters = {
    "table_type"     = "ICEBERG"
    "format_version" = "2"
  }

  storage_descriptor {
    location = "s3://${aws_s3_bucket.iceberg_warehouse.bucket}/logistics_events/"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "event_id"
      type = "string"
    }
    columns {
      name = "event_type"
      type = "string"
    }
    columns {
      name = "route"
      type = "string"
    }
    columns {
      name = "origin"
      type = "string"
    }
    columns {
      name = "destination"
      type = "string"
    }
    columns {
      name = "carrier"
      type = "string"
    }
    columns {
      name = "commodity"
      type = "string"
    }
    columns {
      name = "status"
      type = "string"
    }
    columns {
      name = "estimated_delay_days"
      type = "double"
    }
    columns {
      name = "impact_severity"
      type = "string"
    }
    columns {
      name = "cost_impact_estimate"
      type = "double"
    }
    columns {
      name = "description"
      type = "string"
    }
    columns {
      name = "created_at"
      type = "timestamp"
    }
  }
}

resource "aws_glue_catalog_table" "tariff_regulations" {
  name          = "tariff_regulations"
  database_name = aws_glue_catalog_database.vantage.name

  table_type = "ICEBERG"
  parameters = {
    "table_type"     = "ICEBERG"
    "format_version" = "2"
  }

  storage_descriptor {
    location = "s3://${aws_s3_bucket.iceberg_warehouse.bucket}/tariff_regulations/"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "reg_id"
      type = "string"
    }
    columns {
      name = "regulation_type"
      type = "string"
    }
    columns {
      name = "imposing_country"
      type = "string"
    }
    columns {
      name = "target_country"
      type = "string"
    }
    columns {
      name = "commodity_code"
      type = "string"
    }
    columns {
      name = "commodity_name"
      type = "string"
    }
    columns {
      name = "rate_percent"
      type = "double"
    }
    columns {
      name = "effective_date"
      type = "string"
    }
    columns {
      name = "status"
      type = "string"
    }
    columns {
      name = "description"
      type = "string"
    }
    columns {
      name = "created_at"
      type = "timestamp"
    }
  }
}

resource "aws_glue_catalog_table" "intelligence_briefings" {
  name          = "intelligence_briefings"
  database_name = aws_glue_catalog_database.vantage.name

  table_type = "ICEBERG"
  parameters = {
    "table_type"     = "ICEBERG"
    "format_version" = "2"
  }

  storage_descriptor {
    location = "s3://${aws_s3_bucket.iceberg_warehouse.bucket}/intelligence_briefings/"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "briefing_id"
      type = "string"
    }
    columns {
      name = "generated_at"
      type = "timestamp"
    }
    columns {
      name = "scope"
      type = "string"
    }
    columns {
      name = "scope_value"
      type = "string"
    }
    columns {
      name = "summary"
      type = "string"
    }
    columns {
      name = "risk_assessment"
      type = "string"
    }
    columns {
      name = "opportunities"
      type = "string"
    }
    columns {
      name = "recommendations"
      type = "string"
    }
    columns {
      name = "confidence_score"
      type = "double"
    }
    columns {
      name = "source_data_references"
      type = "string"
    }
  }
}

resource "aws_glue_catalog_table" "concentration_metrics" {
  name          = "concentration_metrics"
  database_name = aws_glue_catalog_database.vantage.name

  table_type = "ICEBERG"
  parameters = {
    "table_type"     = "ICEBERG"
    "format_version" = "2"
  }

  storage_descriptor {
    location = "s3://${aws_s3_bucket.iceberg_warehouse.bucket}/concentration_metrics/"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "commodity_code"
      type = "string"
    }
    columns {
      name = "commodity_name"
      type = "string"
    }
    columns {
      name = "trade_direction"
      type = "string"
    }
    columns {
      name = "trade_year"
      type = "int"
    }
    columns {
      name = "country_count"
      type = "int"
    }
    columns {
      name = "hhi_index"
      type = "double"
    }
    columns {
      name = "concentration_rating"
      type = "string"
    }
    columns {
      name = "max_country_share_pct"
      type = "double"
    }
    columns {
      name = "computed_at"
      type = "timestamp"
    }
  }
}

# ============================================================
# Athena Workgroup
# ============================================================

resource "aws_athena_workgroup" "vantage" {
  name = "${var.project_name}-wg"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_output.bucket}/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

# ============================================================
# IAM Role for Lambda
# ============================================================

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.project_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "lambda" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject", "s3:PutObject", "s3:ListBucket",
          "athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults",
          "glue:*",
          "bedrock:Converse",
          "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================================
# Lambda Functions
# ============================================================

resource "aws_lambda_function" "comtrade_ingestion" {
  function_name = "${var.project_name}-comtrade-ingestion"
  role          = aws_iam_role.lambda.arn
  handler       = "src.lambda.comtrade_ingestion_handler.handler"
  runtime       = "python3.12"
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      RAW_BUCKET      = aws_s3_bucket.raw.id
      GLUE_DATABASE   = var.glue_database
      UN_COMTRADE_KEY = var.un_comtrade_key
      AWS_REGION      = var.aws_region
      ATHENA_OUTPUT   = "s3://${aws_s3_bucket.athena_output.bucket}/"
    }
  }
}

resource "aws_lambda_function" "intelligence" {
  function_name = "${var.project_name}-intelligence"
  role          = aws_iam_role.lambda.arn
  handler       = "src.lambda.intelligence_handler.handler"
  runtime       = "python3.12"
  timeout       = 300
  memory_size   = 1024

  environment {
    variables = {
      RAW_BUCKET       = aws_s3_bucket.raw.id
      GLUE_DATABASE    = var.glue_database
      AWS_REGION       = var.aws_region
      BEDROCK_MODEL_ID = var.bedrock_model_id
      ATHENA_OUTPUT    = "s3://${aws_s3_bucket.athena_output.bucket}/"
    }
  }
}

# ============================================================
# EventBridge Rules
# ============================================================

resource "aws_cloudwatch_event_rule" "weekly_comtrade_sync" {
  name                = "${var.project_name}-weekly-comtrade"
  description         = "Weekly UN Comtrade data sync on Mondays at 2 AM UTC"
  schedule_expression = "cron(0 2 ? * MON *)"
}

resource "aws_cloudwatch_event_target" "weekly_comtrade_sync" {
  rule      = aws_cloudwatch_event_rule.weekly_comtrade_sync.name
  target_id = "comtrade-ingestion"
  arn       = aws_lambda_function.comtrade_ingestion.arn
}

resource "aws_lambda_permission" "weekly_comtrade" {
  statement_id  = "AllowEventBridgeInvokeComtrade"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.comtrade_ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_comtrade_sync.arn
}

resource "aws_cloudwatch_event_rule" "daily_intelligence" {
  name                = "${var.project_name}-daily-intelligence"
  description         = "Daily supply chain intelligence analysis at 6 AM UTC"
  schedule_expression = "cron(0 6 * * ? *)"
}

resource "aws_cloudwatch_event_target" "daily_intelligence" {
  rule      = aws_cloudwatch_event_rule.daily_intelligence.name
  target_id = "intelligence"
  arn       = aws_lambda_function.intelligence.arn
}

resource "aws_lambda_permission" "daily_intelligence" {
  statement_id  = "AllowEventBridgeInvokeIntelligence"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.intelligence.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_intelligence.arn
}

# ============================================================
# Step Functions State Machine
# ============================================================

resource "aws_iam_role" "step_functions" {
  name = "${var.project_name}-sf-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "step_functions" {
  name = "${var.project_name}-sf-policy"
  role = aws_iam_role.step_functions.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["lambda:InvokeFunction"]
      Resource = [
        aws_lambda_function.comtrade_ingestion.arn,
        aws_lambda_function.intelligence.arn,
      ]
    }]
  })
}

resource "aws_sfn_state_machine" "vantage_pipeline" {
  name     = "${var.project_name}-pipeline"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    Comment = "Scope.Vantage Supply Chain Intelligence Pipeline"
    StartAt = "IngestComtrade"
    States = {
      "IngestComtrade" = {
        Type     = "Task"
        Resource = aws_lambda_function.comtrade_ingestion.arn
        Parameters = {
          "reporter.$"  = "$.reporter"
          "partner.$"   = "$.partner"
          "hs_codes.$"  = "$.hs_codes"
          "year.$"      = "$.year"
          "direction"   = "all"
        }
        ResultPath = "$.ingestion"
        Next       = "ComputeScores"
      }
      "ComputeScores" = {
        Type     = "Task"
        Resource = aws_lambda_function.intelligence.arn
        Parameters = {
          "step"         = "compute_scores"
          "commodities.$" = "$.commodities"
        }
        ResultPath = "$.scores"
        Next       = "BedrockAnalysis"
      }
      "BedrockAnalysis" = {
        Type     = "Task"
        Resource = aws_lambda_function.intelligence.arn
        Parameters = {
          "step"    = "bedrock_analysis"
          "scores.$" = "$.scores.body"
        }
        ResultPath = "$.analysis"
        Next       = "WriteBriefings"
      }
      "WriteBriefings" = {
        Type     = "Task"
        Resource = aws_lambda_function.intelligence.arn
        Parameters = {
          "step"    = "write_briefings"
          "scores.$" = "$.analysis.body"
        }
        End = true
      }
    }
  })
}
