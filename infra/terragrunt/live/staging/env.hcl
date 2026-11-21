# Everything that differs between environments. Each stack under live/staging reads this.
locals {
  name               = "data-simulator-api-staging"
  github_environment = "staging"

  # Where the public URL is published for other projects (see front-door).
  url_parameter_name = "/services/data-simulator-api/staging/url"

  deployment_config = "CodeDeployDefault.LambdaAllAtOnce"

  # Staging only sees deploys and smoke tests: its errors don't email, and its limits are
  # much lower.
  alert_topic_name = null

  reserved_concurrency          = 1
  requests_per_5_minutes_per_ip = 100
  max_invocations_per_5_minutes = 200
  max_invocations_per_day       = 2000
}
