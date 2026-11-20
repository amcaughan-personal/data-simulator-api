# Everything that differs between environments. Each stack under live/prod reads this.
locals {
  name               = "data-simulator-api"
  github_environment = "production"

  # Shift 10% of traffic to a new version for 5 minutes, then all of it; roll back if
  # the error alarm fires.
  deployment_config = "CodeDeployDefault.LambdaCanary10Percent5Minutes"

  reserved_concurrency          = 2
  requests_per_5_minutes_per_ip = 100
  max_invocations_per_5_minutes = 1000
  max_invocations_per_day       = 20000
}
