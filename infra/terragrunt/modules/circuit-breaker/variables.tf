variable "name" {
  type = string
}

variable "target_function_name" {
  description = "Function to stop when an alarm fires."
  type        = string
}

variable "target_function_arn" {
  type = string
}

variable "max_invocations_per_5_minutes" {
  description = "Trips on a burst. With concurrency 2 the function can do roughly 1,000+ a minute, so this is sustained heavy use."
  type        = number
  default     = 1000
}

variable "max_invocations_per_day" {
  description = "Trips on slow, sustained use that stays under the burst limit."
  type        = number
  default     = 20000
}

variable "alert_topic_name" {
  description = "Existing SNS topic (from personal-infra) that emails when the breaker trips."
  type        = string
  default     = "security-alerts"
}
