variable "name" {
  type = string
}

variable "origin_domain" {
  description = "Host name of the API function URL."
  type        = string
}

variable "origin_secret" {
  description = "Sent to the origin as X-Origin-Verify; the API rejects requests without it."
  type        = string
  sensitive   = true
}

variable "requests_per_5_minutes_per_ip" {
  description = "Above this, an IP is blocked (403) until its rate drops again."
  type        = number
  default     = 100
}
