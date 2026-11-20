# The API as a Lambda function with a function URL. Whatever sits in front of it (the
# front-door stack) must send the origin secret in X-Origin-Verify; the app rejects
# everything else, so the function URL is useless to call directly.

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

resource "aws_iam_role" "this" {
  name               = "${var.function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
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
  runtime       = "python3.12"
  architectures = ["arm64"]
  handler       = "data_simulator.lambda_handler.handler"

  filename         = var.package_path
  source_code_hash = filebase64sha256(var.package_path)

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
}

resource "aws_lambda_function_url" "this" {
  #checkov:skip=CKV_AWS_258:No IAM auth by design: CloudFront can't sign POST bodies for Lambda origins without per-request-billed Lambda@Edge. The app rejects requests without the origin secret instead.
  function_name      = aws_lambda_function.this.function_name
  authorization_type = "NONE" # access is controlled by the origin secret instead
}

# A function URL without IAM auth needs both of these in the function's resource policy.
resource "aws_lambda_permission" "function_url" {
  #checkov:skip=CKV_AWS_301:Public URL permission is required for a function URL without IAM auth; requests still need the origin secret
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.this.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "invoke_via_url" {
  #checkov:skip=CKV_AWS_301:Same as the function URL permission above
  statement_id             = "AllowInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.this.function_name
  principal                = "*"
  invoked_via_function_url = true
}
