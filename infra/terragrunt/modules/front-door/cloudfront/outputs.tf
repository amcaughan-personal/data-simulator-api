output "url" {
  description = "Public base URL of the API."
  value       = "https://${aws_cloudfront_distribution.this.domain_name}/"
}

output "distribution_id" {
  value = aws_cloudfront_distribution.this.id
}

output "web_acl_name" {
  value = aws_wafv2_web_acl.this.name
}

output "pricing_plan_status" {
  value = aws_pricingplanmanager_subscription.free.status
}
