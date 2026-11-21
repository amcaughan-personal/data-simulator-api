include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/infra/terragrunt/modules/smoke-test"
}

dependency "front_door" {
  config_path = "../front-door"

  mock_outputs                            = { url = "https://example.cloudfront.net/" }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

# Production only: staging is exercised by every deploy.
inputs = {
  name     = "data-sim-api-smoke"
  api_url  = dependency.front_door.outputs.url
  schedule = "cron(0 9 * * ? *)" # daily, 09:00 UTC
}
