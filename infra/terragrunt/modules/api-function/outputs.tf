output "function_name" {
  value = aws_lambda_function.this.function_name
}

output "function_url" {
  value = aws_lambda_function_url.this.function_url
}

output "function_url_domain" {
  description = "Host name of the function URL, for use as an origin."
  value       = split("/", aws_lambda_function_url.this.function_url)[2]
}

output "origin_secret" {
  description = "Value the front door must send in the X-Origin-Verify header."
  value       = random_password.origin_secret.result
  sensitive   = true
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.this.name
}
