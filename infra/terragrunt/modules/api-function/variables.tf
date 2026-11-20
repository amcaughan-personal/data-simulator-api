variable "function_name" {
  type = string
}

variable "package_path" {
  description = "Path to the zip built by scripts/build-lambda.sh."
  type        = string
}

variable "memory_mb" {
  type    = number
  default = 512
}

variable "timeout_seconds" {
  type    = number
  default = 10
}

variable "reserved_concurrency" {
  description = "Hard cap on simultaneous executions; requests beyond it are throttled (and not billed). 0 disables the function."
  type        = number
  default     = 2
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}
