# Circuit breaker: if the API is invoked far more than normal, stop it (reserved
# concurrency 0) and email. The front door already caps cost per IP; this caps it overall.

data "aws_caller_identity" "current" {}

data "aws_sns_topic" "alerts" {
  name = var.alert_topic_name
}

# --------------------------------------------------------------------------------------
# Breaker function: can change concurrency on the API function and nothing else
# --------------------------------------------------------------------------------------

data "archive_file" "breaker" {
  type        = "zip"
  source_file = "${path.module}/breaker.py"
  output_path = "${path.module}/.build/breaker.zip"
}

resource "aws_cloudwatch_log_group" "breaker" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = 30
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "breaker" {
  statement {
    sid       = "StopTheApiFunction"
    actions   = ["lambda:PutFunctionConcurrency"]
    resources = [var.target_function_arn]
  }
  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.breaker.arn}:*"]
  }
}

# Carries personal-infra's permissions boundary for this repo, like every role here: CI
# applies can create and change roles only with it, and it caps what they can do.
resource "aws_iam_role" "breaker" {
  name                 = "${var.name}-role"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  permissions_boundary = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/${var.permissions_boundary_name}"
}

resource "aws_iam_role_policy" "breaker" {
  name   = "stop-api-function"
  role   = aws_iam_role.breaker.id
  policy = data.aws_iam_policy_document.breaker.json
}

resource "aws_lambda_function" "breaker" {
  #checkov:skip=CKV_AWS_116:Invoked by alarms that also email, so a failed run is already visible; a DLQ would add nothing
  #checkov:skip=CKV_AWS_117:No VPC: it only calls the Lambda API
  #checkov:skip=CKV_AWS_50:X-Ray tracing isn't needed for a one-call function
  #checkov:skip=CKV_AWS_272:Code signing adds a signing profile and process for no real gain here
  #checkov:skip=CKV_AWS_173:The only env var is the target function's name, not a secret
  function_name = var.name
  role          = aws_iam_role.breaker.arn
  runtime       = "python3.14"
  architectures = ["arm64"]
  handler       = "breaker.handler"

  filename         = data.archive_file.breaker.output_path
  source_code_hash = data.archive_file.breaker.output_base64sha256

  memory_size                    = 128
  timeout                        = 10
  reserved_concurrent_executions = 1

  environment {
    variables = {
      TARGET_FUNCTION = var.target_function_name
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.breaker.name
  }

  depends_on = [aws_iam_role_policy.breaker]
}

# --------------------------------------------------------------------------------------
# Alarms: either one stops the API and emails
# --------------------------------------------------------------------------------------

locals {
  alarms = {
    burst = {
      description = "API invoked more than ${var.max_invocations_per_5_minutes} times in 5 minutes"
      period      = 300
      threshold   = var.max_invocations_per_5_minutes
    }
    daily = {
      description = "API invoked more than ${var.max_invocations_per_day} times in a day"
      period      = 86400
      threshold   = var.max_invocations_per_day
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "invocations" {
  for_each = local.alarms

  alarm_name          = "${var.name}-${each.key}"
  alarm_description   = "${each.value.description}. The circuit breaker set its concurrency to 0; re-apply the api-function stack to turn it back on."
  namespace           = "AWS/Lambda"
  metric_name         = "Invocations"
  dimensions          = { FunctionName = var.target_function_name }
  statistic           = "Sum"
  period              = each.value.period
  evaluation_periods  = 1
  threshold           = each.value.threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_lambda_function.breaker.arn, data.aws_sns_topic.alerts.arn]
}

resource "aws_lambda_permission" "alarms" {
  for_each = local.alarms

  statement_id  = "AllowAlarm-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.breaker.function_name
  principal     = "lambda.alarms.cloudwatch.amazonaws.com"
  source_arn    = aws_cloudwatch_metric_alarm.invocations[each.key].arn
}
