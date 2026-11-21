include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  env = read_terragrunt_config(find_in_parent_folders("env.hcl")).locals
}

# The public entry point. To use a different front door (e.g. API Gateway), point this
# at another module under modules/front-door/ that takes the same two inputs.
terraform {
  source = "${get_repo_root()}/infra/terragrunt/modules/front-door/cloudfront"
}

dependency "api_function" {
  config_path = "../api-function"

  mock_outputs = {
    function_url_domain = "example.lambda-url.us-east-2.on.aws"
    origin_secret       = "mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  name          = local.env.name
  origin_domain = dependency.api_function.outputs.function_url_domain
  origin_secret = dependency.api_function.outputs.origin_secret

  requests_per_5_minutes_per_ip = local.env.requests_per_5_minutes_per_ip
  url_parameter_name            = local.env.url_parameter_name
}
