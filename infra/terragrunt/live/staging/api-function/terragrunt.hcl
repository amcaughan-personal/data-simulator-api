include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  env = read_terragrunt_config(find_in_parent_folders("env.hcl")).locals
}

terraform {
  source = "${get_repo_root()}/infra/terragrunt/modules/api-function"
}

inputs = {
  function_name        = local.env.name
  package_path         = "${get_repo_root()}/dist/lambda.zip" # built by scripts/build-lambda.sh
  memory_mb            = 512
  timeout_seconds      = 10
  reserved_concurrency = local.env.reserved_concurrency

  environment_variables = {
    DATA_SIMULATOR_MAX_CELLS = "100000"
  }
}
