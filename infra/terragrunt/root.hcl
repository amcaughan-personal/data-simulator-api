# Tool versions are set once, in the repo's .tool-versions (also read by the dev container and
# CI). Running with any other version stops here instead of drifting.
terraform_version_constraint  = "= ${local.tool_versions.terraform}"
terragrunt_version_constraint = "= ${local.tool_versions.terragrunt}"

locals {
  tool_versions = {
    for line in split("\n", file("${get_repo_root()}/.tool-versions")) :
    split(" ", trimspace(line))[0] => split(" ", trimspace(line))[1]
    if length(regexall("^[a-z]", trimspace(line))) > 0
  }

  aws_region = "us-east-2"

  # On every taggable resource, so anything in the console points back to the code
  # that manages it: the repo, and the Terragrunt stack within it.
  common_tags = {
    Repo      = "amcaughan-personal/data-simulator-api"
    Stack     = path_relative_to_include() # e.g. live/prod/api-function
    ManagedBy = "terragrunt"
    Owner     = "amcaughan"
  }
}

remote_state {
  backend = "s3"

  config = {
    bucket       = "amcaughan-tf-state-us-east-2"
    key          = "data-simulator-api/${path_relative_to_include()}/terraform.tfstate"
    region       = local.aws_region
    encrypt      = true
    use_lockfile = true
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"

  contents = <<EOF
variable "extra_default_tags" {
  type    = map(string)
  default = {}
}

provider "aws" {
  region  = "${local.aws_region}"

  default_tags {
    tags = merge(${jsonencode(local.common_tags)}, var.extra_default_tags)
  }
}

# Some global services live in us-east-1 (e.g. WAF for CloudFront). Same tags.
provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"

  default_tags {
    tags = merge(${jsonencode(local.common_tags)}, var.extra_default_tags)
  }
}
EOF
}

generate "backend_stub" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"

  contents = <<EOF
terraform {
  backend "s3" {}
}
EOF
}
