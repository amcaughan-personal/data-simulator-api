output "parameter_names" {
  value = [for parameter in aws_ssm_parameter.this : parameter.name]
}
