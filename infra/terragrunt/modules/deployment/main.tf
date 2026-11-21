# How new code reaches traffic. CI uploads code, publishes a version and asks CodeDeploy to
# move the `live` alias to it, using this environment's deployment config (all at once in
# staging, a 10% canary in production). If the alias's error alarm fires during a
# deployment, CodeDeploy moves the alias back.
#
# CI signs in through GitHub's OIDC provider (managed in personal-infra) as a role that
# only jobs in this GitHub environment can use, and that can only deploy this function.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

locals {
  account = data.aws_caller_identity.current.account_id
  region  = data.aws_region.current.region
  arn     = "arn:${data.aws_partition.current.partition}"
}

# --------------------------------------------------------------------------------------
# Errors from the live alias: failed invocations, plus requests answered with a 5xx (an
# unhandled exception in the app returns a 500 without failing the invocation). During a
# deployment, CodeDeploy rolls back when this fires; with alert_topic_name set, it also emails.
# --------------------------------------------------------------------------------------

data "aws_sns_topic" "alerts" {
  count = var.alert_topic_name == null ? 0 : 1
  name  = var.alert_topic_name
}

resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.function_name}-live-errors"
  alarm_description   = "Failed invocations or 5xx responses from ${var.function_name}:${var.alias_name}. During a deployment, CodeDeploy rolls back when this fires."
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = data.aws_sns_topic.alerts[*].arn

  metric_query {
    id          = "errors"
    expression  = "FILL(failed, 0) + FILL(server_errors, 0)"
    label       = "Failed invocations + 5xx responses"
    return_data = true
  }

  metric_query {
    id = "failed"
    metric {
      namespace   = "AWS/Lambda"
      metric_name = "Errors"
      dimensions  = { FunctionName = var.function_name, Resource = "${var.function_name}:${var.alias_name}" }
      stat        = "Sum"
      period      = 60
    }
  }

  metric_query {
    id = "server_errors"
    metric {
      namespace   = "AWS/Lambda"
      metric_name = "Url5xxCount"
      dimensions  = { FunctionName = var.function_name, Resource = "${var.function_name}:${var.alias_name}" }
      stat        = "Sum"
      period      = 60
    }
  }
}

# --------------------------------------------------------------------------------------
# CodeDeploy: shifts the alias, and can do nothing else
# --------------------------------------------------------------------------------------

data "aws_iam_policy_document" "codedeploy_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codedeploy.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "codedeploy" {
  #checkov:skip=CKV_AWS_356:DescribeAlarms is read-only, and CodeDeploy calls it in a way that only "*" allows
  statement {
    sid       = "MoveTheAlias"
    actions   = ["lambda:GetAlias", "lambda:UpdateAlias", "lambda:GetFunction"]
    resources = [var.function_arn, "${var.function_arn}:*"]
  }
  statement {
    # Read-only, and DescribeAlarms can't be limited to particular alarms.
    sid       = "ReadAlarmState"
    actions   = ["cloudwatch:DescribeAlarms"]
    resources = ["*"]
  }
}

resource "aws_iam_role" "codedeploy" {
  name               = "${var.function_name}-codedeploy"
  assume_role_policy = data.aws_iam_policy_document.codedeploy_assume.json
}

resource "aws_iam_role_policy" "codedeploy" {
  name   = "shift-live-alias"
  role   = aws_iam_role.codedeploy.id
  policy = data.aws_iam_policy_document.codedeploy.json
}

resource "aws_codedeploy_app" "this" {
  name             = var.function_name
  compute_platform = "Lambda"
}

resource "aws_codedeploy_deployment_group" "live" {
  app_name               = aws_codedeploy_app.this.name
  deployment_group_name  = var.alias_name
  service_role_arn       = aws_iam_role.codedeploy.arn
  deployment_config_name = var.deployment_config

  deployment_style {
    deployment_type   = "BLUE_GREEN"
    deployment_option = "WITH_TRAFFIC_CONTROL"
  }

  alarm_configuration {
    enabled = true
    alarms  = [aws_cloudwatch_metric_alarm.errors.alarm_name]
  }

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM"]
  }
}

# --------------------------------------------------------------------------------------
# The role CI deploys as
# --------------------------------------------------------------------------------------

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "deploy_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only jobs in this GitHub environment (which allows only main, and in production
    # waits for approval) get these credentials.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid = "UploadAndPublishCode"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:PublishVersion",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:GetAlias",
    ]
    resources = [var.function_arn, "${var.function_arn}:*"]
  }
  statement {
    # Only for the first deploy, when the alias still points at $LATEST and there is no
    # version for CodeDeploy to shift from. Lambda authorizes UpdateAlias against the
    # function's ARN.
    sid       = "PointNewAlias"
    actions   = ["lambda:UpdateAlias"]
    resources = [var.function_arn]
  }
  statement {
    sid       = "StartAndWatchDeployments"
    actions   = ["codedeploy:CreateDeployment", "codedeploy:GetDeployment"]
    resources = [aws_codedeploy_deployment_group.live.arn]
  }
  statement {
    sid       = "ReadDeploymentConfig"
    actions   = ["codedeploy:GetDeploymentConfig"]
    resources = ["${local.arn}:codedeploy:${local.region}:${local.account}:deploymentconfig:${var.deployment_config}"]
  }
  statement {
    sid       = "RegisterRevision"
    actions   = ["codedeploy:RegisterApplicationRevision", "codedeploy:GetApplicationRevision"]
    resources = [aws_codedeploy_app.this.arn]
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.function_name}-deploy"
  description          = "GitHub Actions deploys of ${var.function_name} (environment ${var.github_environment})"
  assume_role_policy   = data.aws_iam_policy_document.deploy_assume.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy-${var.function_name}"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
