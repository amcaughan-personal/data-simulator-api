# Infrastructure

Terragrunt/Terraform for running the API on AWS. Applied manually from the local dev
image (`local-dev/dev-shell.sh`); state lives in the shared bucket from `personal_infra`.

```
terragrunt/
  root.hcl                      backend, provider, tags (Repo + Stack on every resource)
  modules/
    api-function/               Lambda + function URL + log group + least-privilege role
  live/prod/
    api-function/               the deployed function
```

The function only answers requests carrying the origin secret, so it is meant to sit
behind a front door (added in its own stack) rather than be called directly.

Deploy:

```bash
./scripts/build-lambda.sh                       # dist/lambda.zip
cd infra/terragrunt/live/prod/api-function && terragrunt apply
```
