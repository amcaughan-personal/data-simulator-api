# Publishes values this repo's GitHub Actions need (URLs, role ARNs) to SSM Parameter
# Store, at /github/<repo>/<environment>/<NAME>. personal-infra's GitHub stack turns every
# parameter under /github/ into a GitHub environment variable with that name, so workflows
# read `vars.NAME` instead of hard-coding values. Only for values that aren't secret.

resource "aws_ssm_parameter" "this" {
  #checkov:skip=CKV2_AWS_34:Not secrets: URLs and ARNs; GitHub masks the ARNs in workflow logs
  for_each = var.variables

  name        = "/github/${var.github_repository}/${var.github_environment}/${each.key}"
  description = "GitHub environment variable ${each.key} for ${var.github_repository} (${var.github_environment})"
  type        = "String"
  value       = each.value
}
