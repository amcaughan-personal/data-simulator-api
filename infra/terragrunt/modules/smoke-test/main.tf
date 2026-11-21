# Scheduled smoke test: a CloudWatch Synthetics canary runs the smoke-test requests against
# the public URL on a schedule, and an alarm emails when a run fails. Everything for it is in
# this stack, so removing it is one destroy.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_sns_topic" "alerts" {
  name = var.alert_topic_name
}

locals {
  bucket = "${var.name}-canary-${data.aws_caller_identity.current.account_id}"
}

# --------------------------------------------------------------------------------------
# Run artifacts (logs, results), kept for two weeks
# --------------------------------------------------------------------------------------

resource "aws_s3_bucket" "artifacts" {
  #checkov:skip=CKV_AWS_18:Access logs for a bucket of canary run logs would only log the canary
  #checkov:skip=CKV_AWS_144:Run artifacts are disposable; replicating them to another region adds cost for nothing
  #checkov:skip=CKV_AWS_145:The AWS-managed key is enough for canary run logs
  #checkov:skip=CKV2_AWS_62:Nothing reacts to new run artifacts
  #checkov:skip=CKV_AWS_21:Artifacts expire after two weeks; versions would only keep them longer
  bucket        = local.bucket
  force_destroy = true # so destroying the stack also removes old runs
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-runs"
    status = "Enabled"
    filter {}
    expiration {
      days = 14
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# --------------------------------------------------------------------------------------
# The canary's role: write its own results, logs and metrics
# --------------------------------------------------------------------------------------

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "canary" {
  statement {
    sid       = "WriteRunArtifacts"
    actions   = ["s3:PutObject", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
  }
  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/cwsyn-${var.name}-*"]
  }
  statement {
    #checkov:skip=CKV_AWS_356:PutMetricData can't be scoped to a resource; it's limited to the Synthetics namespace by the condition
    sid       = "PublishCanaryMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["CloudWatchSynthetics"]
    }
  }
}

resource "aws_iam_role" "canary" {
  name               = "${var.name}-canary"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy" "canary" {
  name   = "canary"
  role   = aws_iam_role.canary.id
  policy = data.aws_iam_policy_document.canary.json
}

# --------------------------------------------------------------------------------------
# The canary and its alarm
# --------------------------------------------------------------------------------------

data "archive_file" "canary" {
  type        = "zip"
  source_dir  = "${path.module}/canary"
  output_path = "${path.module}/.build/canary.zip"
}

resource "aws_synthetics_canary" "this" {
  name                 = var.name
  artifact_s3_location = "s3://${aws_s3_bucket.artifacts.id}/"
  execution_role_arn   = aws_iam_role.canary.arn
  runtime_version      = "syn-python-selenium-14.0"
  handler              = "smoke_test.handler"
  zip_file             = data.archive_file.canary.output_path
  start_canary         = true

  schedule {
    expression = var.schedule
  }

  run_config {
    timeout_in_seconds    = 120
    environment_variables = { API_URL = var.api_url }
  }

  success_retention_period = 14
  failure_retention_period = 14

  depends_on = [aws_iam_role_policy.canary]
}

resource "aws_cloudwatch_metric_alarm" "failed" {
  alarm_name          = "${var.name}-failed"
  alarm_description   = "The scheduled smoke test against ${var.api_url} failed; the canary's run in CloudWatch Synthetics shows which request."
  namespace           = "CloudWatchSynthetics"
  metric_name         = "SuccessPercent"
  dimensions          = { CanaryName = aws_synthetics_canary.this.name }
  statistic           = "Minimum"
  period              = 86400
  evaluation_periods  = 1
  threshold           = 100
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [data.aws_sns_topic.alerts.arn]
}
