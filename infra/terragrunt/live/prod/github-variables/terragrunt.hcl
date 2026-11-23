include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  env = read_terragrunt_config(find_in_parent_folders("env.hcl")).locals
}

terraform {
  source = "${get_repo_root()}/infra/terragrunt/modules/github-variables"
}

dependency "api_function" {
  config_path = "../api-function"

  mock_outputs                            = { function_name = "data-simulator-api" }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "front_door" {
  config_path = "../front-door"

  mock_outputs                            = { url = "https://example.cloudfront.net/" }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  github_repository  = "data-simulator-api"
  github_environment = local.env.github_environment

  # Read by .github/workflows/deploy.yml as vars.<NAME>.
  variables = {
    API_URL       = trimsuffix(dependency.front_door.outputs.url, "/")
    FUNCTION_NAME = dependency.api_function.outputs.function_name
  }
}
