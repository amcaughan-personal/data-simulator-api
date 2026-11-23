include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  env = read_terragrunt_config(find_in_parent_folders("env.hcl")).locals
}

terraform {
  source = "${get_repo_root()}/infra/terragrunt/modules/deployment"
}

dependency "api_function" {
  config_path = "../api-function"

  mock_outputs = {
    function_name = "data-simulator-api"
    function_arn  = "arn:aws:lambda:us-east-2:000000000000:function:data-simulator-api"
    alias_name    = "live"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  function_name      = dependency.api_function.outputs.function_name
  function_arn       = dependency.api_function.outputs.function_arn
  alias_name         = dependency.api_function.outputs.alias_name
  deployment_config  = local.env.deployment_config
  github_environment = local.env.github_environment
  alert_topic_name   = local.env.alert_topic_name

  # GitHub's immutable subject: the org and repo by name and numeric ID. A repo deleted and
  # recreated under the same name gets a new ID, so its tokens can't assume this role.
  oidc_subject_prefix = "repo:amcaughan-personal@271645414/data-simulator-api@1179137908"
}
