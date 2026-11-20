include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  env = read_terragrunt_config(find_in_parent_folders("env.hcl")).locals
}

terraform {
  source = "${get_repo_root()}/infra/terragrunt/modules/circuit-breaker"
}

dependency "api_function" {
  config_path = "../api-function"

  mock_outputs = {
    function_name = "data-simulator-api"
    function_arn  = "arn:aws:lambda:us-east-2:000000000000:function:data-simulator-api"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  name                 = "${local.env.name}-circuit-breaker"
  target_function_name = dependency.api_function.outputs.function_name
  target_function_arn  = dependency.api_function.outputs.function_arn

  max_invocations_per_5_minutes = local.env.max_invocations_per_5_minutes
  max_invocations_per_day       = local.env.max_invocations_per_day
}
