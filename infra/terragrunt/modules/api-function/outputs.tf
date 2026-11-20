output "function_name" {
  value = aws_lambda_function.this.function_name
}

output "function_url" {
  value = aws_lambda_function_url.live.function_url
}

output "function_url_domain" {
  description = "Host name of the live alias's function URL, for use as an origin."
  value       = split("/", aws_lambda_function_url.live.function_url)[2]
}

output "alias_name" {
  value = aws_lambda_alias.live.name
}

output "origin_secret" {
  description = "Value the front door must send in the X-Origin-Verify header."
  value       = random_password.origin_secret.result
  sensitive   = true
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.this.name
}

output "function_arn" {
  value = aws_lambda_function.this.arn
}
