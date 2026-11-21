variable "name" {
  description = "Canary name: lowercase, at most 21 characters."
  type        = string
}

variable "api_url" {
  description = "Public base URL to check."
  type        = string
}

variable "schedule" {
  description = "When to run: a CloudWatch Synthetics cron expression (rate() only goes up to an hour)."
  type        = string
  default     = "cron(0 9 * * ? *)" # daily, 09:00 UTC
}

variable "alert_topic_name" {
  description = "Existing SNS topic (from personal-infra) to email when a run fails."
  type        = string
  default     = "security-alerts"
}
