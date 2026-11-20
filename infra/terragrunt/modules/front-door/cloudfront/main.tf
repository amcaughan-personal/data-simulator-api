# Public front door for the API: CloudFront + WAF on the CloudFront Free flat-rate plan.
# The plan has no overage charges, so this layer costs $0 however much traffic arrives;
# WAF blocks abuse before it reaches the function, and requests it blocks don't even
# count against the plan's allowance.
#
# The Free plan allows up to 5 WAF rules but only some features: per-IP rate limits and
# AWS managed IP lists work; custom block responses, body-size limits and method matching
# are rejected (WAFFeatureNotIncludedInPricingPlanException). The app handles those:
# 405 for other methods, 413 for oversized bodies.

# --------------------------------------------------------------------------------------
# WAF (CloudFront web ACLs live in us-east-1)
# --------------------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "this" {
  #checkov:skip=CKV2_AWS_31:WAF logging: metrics and sampled requests are enough at this scale
  #checkov:skip=CKV_AWS_192:Log4j rule group: the API is Python, no Java anywhere in the path (and the Free plan caps rules at 5)
  provider = aws.us_east_1
  name     = var.name
  scope    = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit-per-ip"
    priority = 0
    action {
      block {} # 403; custom responses (e.g. 429 with a message) need a paid plan tier
    }
    statement {
      rate_based_statement {
        limit                 = var.requests_per_5_minutes_per_ip
        evaluation_window_sec = 300
        aggregate_key_type    = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-rate-limit"
      sampled_requests_enabled   = true
    }
  }



  rule {
    name     = "aws-ip-reputation"
    priority = 1
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesAmazonIpReputationList"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name}-ip-reputation"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = var.name
    sampled_requests_enabled   = true
  }
}

# --------------------------------------------------------------------------------------
# CloudFront
# --------------------------------------------------------------------------------------

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled" # every response is freshly generated
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader" # function URLs need their own Host header
}

data "aws_cloudfront_response_headers_policy" "cors_and_security" {
  name = "Managed-CORS-with-preflight-and-SecurityHeadersPolicy"
}

resource "aws_cloudfront_distribution" "this" {
  #checkov:skip=CKV_AWS_374:Geo restriction: it's a public demo API
  #checkov:skip=CKV_AWS_86:Access logs: WAF metrics and sampled requests are enough at this scale
  #checkov:skip=CKV_AWS_310:Origin failover: there is a single origin
  #checkov:skip=CKV_AWS_305:Default root object is for static sites; / redirects to /docs
  #checkov:skip=CKV_AWS_174:Default *.cloudfront.net certificate, whose TLS policy can't be changed; a custom domain would allow TLS 1.2+
  #checkov:skip=CKV2_AWS_42:Same: no custom domain
  #checkov:skip=CKV2_AWS_47:Log4j rules: no Java anywhere in the path
  enabled         = true
  comment         = var.name
  is_ipv6_enabled = true
  http_version    = "http2and3"
  web_acl_id      = aws_wafv2_web_acl.this.arn

  origin {
    origin_id   = "api-function"
    domain_name = var.origin_domain

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
      origin_read_timeout    = 30
    }

    # Replaces any header of the same name a client sends.
    custom_header {
      name  = "X-Origin-Verify"
      value = var.origin_secret
    }
  }

  default_cache_behavior {
    target_origin_id       = "api-function"
    viewer_protocol_policy = "https-only"                                                 # don't silently redirect POSTs from http
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"] # WAF narrows this
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.cors_and_security.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# --------------------------------------------------------------------------------------
# CloudFront Free flat-rate plan: $0/month, no overage charges
# --------------------------------------------------------------------------------------

resource "aws_pricingplanmanager_subscription" "free" {
  provider    = aws.us_east_1
  plan_family = "CloudFront"
  plan_tier   = "FREE"
  resource_arns = [
    aws_cloudfront_distribution.this.arn,
    aws_wafv2_web_acl.this.arn,
  ]
}
