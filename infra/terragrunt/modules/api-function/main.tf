# The API as a Lambda function behind a `live` alias with a function URL. Whatever sits in
# front of it (the front-door stack) must send the origin secret in X-Origin-Verify; the
# app rejects everything else, so the function URL is useless to call directly.
#
# Terraform owns the function's configuration; CI owns its code. Deploys upload code,
# publish a numbered version and move the alias to it through CodeDeploy (the deployment
# stack). Configuration changes made here reach traffic with the next deploy, because
# each published version keeps the configuration it was published with.

data "aws_caller_identity" "current" {}

resource "random_password" "origin_secret" {
  length  = 48
  special = false
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
}

# The function can write its own logs and nothing else.
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "logs" {
  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }
}

# Carries personal-infra's permissions boundary for this repo, like every role here: CI
# applies can create and change roles only with it, and it caps what they can do.
resource "aws_iam_role" "this" {
  name                 = "${var.function_name}-role"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  permissions_boundary = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/${var.permissions_boundary_name}"
}

resource "aws_iam_role_policy" "logs" {
  name   = "write-own-logs"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.logs.json
}

resource "aws_lambda_function" "this" {
  #checkov:skip=CKV_AWS_116:Only invoked synchronously (via its URL), so a dead-letter queue would never receive anything
  #checkov:skip=CKV_AWS_117:No VPC: the function calls nothing, so a VPC would add cost without isolating anything
  #checkov:skip=CKV_AWS_50:X-Ray tracing isn't needed for a single small function
  #checkov:skip=CKV_AWS_272:Code signing adds a signing profile and process for no real gain here
  #checkov:skip=CKV_AWS_173:Default encryption is enough for the only env secret (the origin header value)
  function_name = var.function_name
  role          = aws_iam_role.this.arn
  runtime       = "python3.14"
  architectures = ["arm64"]
  handler       = "data_simulator.lambda_handler.handler"

  filename = var.package_path

  memory_size                    = var.memory_mb
  timeout                        = var.timeout_seconds
  reserved_concurrent_executions = var.reserved_concurrency

  environment {
    variables = merge(var.environment_variables, {
      DATA_SIMULATOR_ORIGIN_SECRET = random_password.origin_secret.result
    })
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.this.name
  }

  depends_on = [aws_iam_role_policy.logs]

  lifecycle {
    # The package here is only for creating the function (build it first with
    # scripts/build-lambda.sh); deploys own the code after that.
    ignore_changes = [filename]
  }
}

# Traffic always goes through this alias. Deploys point it at new versions (gradually, in
# production), so Terraform sets it only at creation.
resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.this.function_name
  function_version = "$LATEST"

  lifecycle {
    ignore_changes = [function_version, routing_config]
  }
}

resource "aws_lambda_function_url" "live" {
  #checkov:skip=CKV_AWS_258:No IAM auth by design: CloudFront can't sign POST bodies for Lambda origins without per-request-billed Lambda@Edge. The app rejects requests without the origin secret instead.
  function_name      = aws_lambda_function.this.function_name
  qualifier          = aws_lambda_alias.live.name
  authorization_type = "NONE" # access is controlled by the origin secret instead
}

resource "aws_lambda_permission" "live_function_url" {
  #checkov:skip=CKV_AWS_301:Public URL permission is required for a function URL without IAM auth; requests still need the origin secret
  statement_id           = "AllowPublicFunctionUrlLive"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.this.function_name
  qualifier              = aws_lambda_alias.live.name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "live_invoke_via_url" {
  #checkov:skip=CKV_AWS_301:Same as the function URL permission above
  statement_id             = "AllowInvokeViaFunctionUrlLive"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.this.function_name
  qualifier                = aws_lambda_alias.live.name
  principal                = "*"
  invoked_via_function_url = true

  # Lambda rejects concurrent permission changes on one function, so add them one at a time.
  depends_on = [aws_lambda_permission.live_function_url]
}
