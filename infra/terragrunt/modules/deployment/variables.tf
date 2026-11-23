variable "function_name" {
  type = string
}

variable "function_arn" {
  type = string
}

variable "alias_name" {
  description = "The alias deploys move between versions."
  type        = string
}

variable "deployment_config" {
  description = "How traffic shifts to a new version, e.g. CodeDeployDefault.LambdaCanary10Percent5Minutes."
  type        = string
}

variable "alert_topic_name" {
  description = "Existing SNS topic (from personal-infra) to email when the error alarm fires; null for no email."
  type        = string
  default     = null
}

variable "permissions_boundary_name" {
  description = "IAM policy attached as the permissions boundary of the roles this module creates."
  type        = string
}
