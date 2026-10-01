locals {
  dashboard_name = "finance-dev"
  dashboard_metric_defaults = {
    accountId = var.finance_account_id
    region    = var.aws_region
    period    = 60
  }
}

data "aws_caller_identity" "admin" {
  provider = aws.admin
}

resource "aws_oam_sink" "finance_monitoring" {
  provider = aws.admin
  name     = "finance-dev-monitoring"

  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.admin.account_id == var.admin_account_id
      error_message = "The admin provider must authenticate to admin_account_id."
    }
  }
}

resource "aws_oam_sink_policy" "finance_monitoring" {
  provider        = aws.admin
  sink_identifier = aws_oam_sink.finance_monitoring.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowFinanceDevLink"
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${var.finance_account_id}:root" }
      Action    = ["oam:CreateLink", "oam:UpdateLink"]
      Resource  = "*"
      Condition = {
        "ForAllValues:StringEquals" = {
          "oam:ResourceTypes" = [
            "AWS::CloudWatch::Metric",
            "AWS::Logs::LogGroup",
          ]
        }
      }
    }]
  })
}

resource "aws_oam_link" "finance_dev" {
  sink_identifier = aws_oam_sink.finance_monitoring.arn
  label_template  = "$AccountName"
  resource_types = [
    "AWS::CloudWatch::Metric",
    "AWS::Logs::LogGroup",
  ]

  depends_on = [aws_oam_sink_policy.finance_monitoring]
}

resource "aws_iam_role_policy" "worker_cloudwatch_metrics" {
  name = "${var.project_name}-worker-cloudwatch-metrics"
  role = module.worker.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "PublishFinanceAndSystemMetrics"
      Effect   = "Allow"
      Action   = "cloudwatch:PutMetricData"
      Resource = "*"
      Condition = {
        StringEquals = {
          "cloudwatch:namespace" = ["CWAgent", "FinanceDev/Ingestion"]
        }
      }
    }]
  })
}

resource "aws_iam_user_policy" "monitoring_view" {
  provider = aws.admin
  name     = "FinanceDevCrossAccountMonitoringView"
  user     = var.admin_monitoring_user_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ViewFinanceDevMonitoring"
      Effect = "Allow"
      Action = [
        "cloudwatch:GetDashboard",
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListDashboards",
        "cloudwatch:ListMetrics",
        "oam:Get*",
        "oam:List*",
      ]
      Resource = "*"
    }]
  })
}

resource "aws_cloudwatch_dashboard" "finance_dev" {
  provider       = aws.admin
  dashboard_name = local.dashboard_name
  dashboard_body = jsonencode({
    start          = "-PT6H"
    periodOverride = "inherit"
    widgets = [
      {
        type       = "text", x = 0, y = 0, width = 24, height = 2
        properties = { markdown = "# FINANCE-DEV\nInfrastructure and ingestion health" }
      },
      {
        type       = "text", x = 0, y = 2, width = 24, height = 1
        properties = { markdown = "## SYSTEM" }
      },
      {
        type = "metric", x = 0, y = 3, width = 6, height = 6
        properties = merge(local.dashboard_metric_defaults, {
          title   = "EC2 CPU", view = "timeSeries", stat = "Average", yAxis = { left = { min = 0, max = 100 } }
          metrics = [["AWS/EC2", "CPUUtilization", "InstanceId", module.worker.instance_id]]
        })
      },
      {
        type = "metric", x = 6, y = 3, width = 6, height = 6
        properties = merge(local.dashboard_metric_defaults, {
          title   = "EC2 RAM", view = "timeSeries", stat = "Average", yAxis = { left = { min = 0, max = 100 } }
          metrics = [["CWAgent", "mem_used_percent", "InstanceId", module.worker.instance_id]]
        })
      },
      {
        type = "metric", x = 12, y = 3, width = 6, height = 6
        properties = merge(local.dashboard_metric_defaults, {
          title   = "Root Disk", view = "timeSeries", stat = "Average", yAxis = { left = { min = 0, max = 100 } }
          metrics = [["CWAgent", "disk_used_percent", "InstanceId", module.worker.instance_id, "path", "/", "fstype", "xfs"]]
        })
      },
      {
        type = "metric", x = 18, y = 3, width = 6, height = 6
        properties = merge(local.dashboard_metric_defaults, {
          title = "EC2 Network", view = "timeSeries", stat = "Sum"
          metrics = [
            ["AWS/EC2", "NetworkIn", "InstanceId", module.worker.instance_id],
            ["AWS/EC2", "NetworkOut", "InstanceId", module.worker.instance_id],
          ]
        })
      },
      {
        type       = "text", x = 0, y = 9, width = 24, height = 1
        properties = { markdown = "## DATABASE" }
      },
      {
        type = "metric", x = 0, y = 10, width = 6, height = 5
        properties = merge(local.dashboard_metric_defaults, {
          title   = "RDS CPU", view = "singleValue", stat = "Average"
          metrics = [["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", module.rds.identifier]]
        })
      },
      {
        type = "metric", x = 6, y = 10, width = 6, height = 5
        properties = merge(local.dashboard_metric_defaults, {
          title = "RDS Free Memory (GiB)", view = "singleValue", stat = "Average"
          metrics = [
            [{ expression = "m1/1073741824", label = "Free memory (GiB)", id = "e1" }],
            ["AWS/RDS", "FreeableMemory", "DBInstanceIdentifier", module.rds.identifier, { id = "m1", visible = false }],
          ]
        })
      },
      {
        type = "metric", x = 12, y = 10, width = 6, height = 5
        properties = merge(local.dashboard_metric_defaults, {
          title = "RDS Free Storage (GiB)", view = "singleValue", stat = "Average"
          metrics = [
            [{ expression = "m1/1073741824", label = "Free storage (GiB)", id = "e1" }],
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", module.rds.identifier, { id = "m1", visible = false }],
          ]
        })
      },
      {
        type = "metric", x = 18, y = 10, width = 6, height = 5
        properties = merge(local.dashboard_metric_defaults, {
          title   = "DB Connections", view = "singleValue", stat = "Average"
          metrics = [["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", module.rds.identifier]]
        })
      },
      {
        type = "metric", x = 0, y = 15, width = 12, height = 6
        properties = merge(local.dashboard_metric_defaults, {
          title = "RDS Read / Write IOPS", view = "timeSeries", stat = "Average"
          metrics = [
            ["AWS/RDS", "ReadIOPS", "DBInstanceIdentifier", module.rds.identifier],
            ["AWS/RDS", "WriteIOPS", "DBInstanceIdentifier", module.rds.identifier],
          ]
        })
      },
      {
        type = "metric", x = 12, y = 15, width = 12, height = 6
        properties = merge(local.dashboard_metric_defaults, {
          title   = "DB Connections History", view = "timeSeries", stat = "Average"
          metrics = [["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", module.rds.identifier]]
        })
      },
      {
        type       = "text", x = 0, y = 21, width = 24, height = 1
        properties = { markdown = "## INGESTION" }
      },
      {
        type = "metric", x = 0, y = 22, width = 6, height = 5
        properties = merge(local.dashboard_metric_defaults, {
          title   = "Stock Ingest Age", view = "singleValue", stat = "Maximum"
          metrics = [["FinanceDev/Ingestion", "StockIngestAgeSeconds"]]
        })
      },
      {
        type = "metric", x = 6, y = 22, width = 6, height = 5
        properties = merge(local.dashboard_metric_defaults, {
          title   = "Options Rows / Minute", view = "singleValue", stat = "Sum", period = 60
          metrics = [["FinanceDev/Ingestion", "OptionsRowsIngested"]]
        })
      },
      {
        type = "metric", x = 12, y = 22, width = 6, height = 5
        properties = merge(local.dashboard_metric_defaults, {
          title   = "News Articles / Hour", view = "singleValue", stat = "Sum", period = 3600
          metrics = [["FinanceDev/Ingestion", "NewsArticlesIngested"]]
        })
      },
      {
        type = "metric", x = 18, y = 22, width = 6, height = 5
        properties = merge(local.dashboard_metric_defaults, {
          title   = "API Failures", view = "singleValue", stat = "Sum"
          metrics = [["FinanceDev/Ingestion", "APIFailures"]]
        })
      },
      {
        type = "metric", x = 0, y = 27, width = 12, height = 6
        properties = merge(local.dashboard_metric_defaults, {
          title   = "Ingestion Errors", view = "timeSeries", stat = "Sum"
          metrics = [["FinanceDev/Ingestion", "IngestionErrors"]]
        })
      },
      {
        type = "metric", x = 12, y = 27, width = 12, height = 6
        properties = merge(local.dashboard_metric_defaults, {
          title = "Worker Execution Time", view = "timeSeries", stat = "Average"
          metrics = [
            ["FinanceDev/Ingestion", "WorkerExecutionTime", "Worker", "stock"],
            ["FinanceDev/Ingestion", "WorkerExecutionTime", "Worker", "options"],
            ["FinanceDev/Ingestion", "WorkerExecutionTime", "Worker", "news"],
            ["FinanceDev/Ingestion", "WorkerExecutionTime", "Worker", "bonds"],
            ["FinanceDev/Ingestion", "WorkerExecutionTime", "Worker", "analyst"],
            ["FinanceDev/Ingestion", "WorkerExecutionTime", "Worker", "insider"],
            ["FinanceDev/Ingestion", "WorkerExecutionTime", "Worker", "government_trades"],
          ]
        })
      },
    ]
  })
}
