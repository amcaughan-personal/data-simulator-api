output "breaker_function_name" {
  value = aws_lambda_function.breaker.function_name
}

output "alarm_names" {
  value = [for alarm in aws_cloudwatch_metric_alarm.invocations : alarm.alarm_name]
}
