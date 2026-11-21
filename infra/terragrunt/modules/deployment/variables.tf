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

variable "github_repository" {
  description = "owner/name of the repository whose workflows deploy."
  type        = string
}

variable "github_environment" {
  description = "Only workflow jobs in this GitHub environment can deploy (see personal-infra)."
  type        = string
}
