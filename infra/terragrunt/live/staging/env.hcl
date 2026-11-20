# Everything that differs between environments. Each stack under live/staging reads this.
locals {
  name               = "data-simulator-api-staging"
  github_environment = "staging"

  deployment_config = "CodeDeployDefault.LambdaAllAtOnce"

  # Staging only sees deploys and smoke tests, so it gets much lower limits.
  reserved_concurrency          = 1
  requests_per_5_minutes_per_ip = 100
  max_invocations_per_5_minutes = 200
  max_invocations_per_day       = 2000
}
