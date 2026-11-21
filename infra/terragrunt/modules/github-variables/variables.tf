variable "github_repository" {
  description = "Repository name (without the owner) the variables are for."
  type        = string
}

variable "github_environment" {
  type = string
}

variable "variables" {
  description = "Variable names (e.g. API_URL) and their values. Not for secrets."
  type        = map(string)
}
