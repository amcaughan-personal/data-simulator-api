# Infrastructure

Terragrunt/Terraform for running the API on AWS. Applied manually from the local dev
image (`local-dev/dev-shell.sh`); state lives in the shared bucket from `personal_infra`.

```
terragrunt/
  root.hcl                      backend, provider, tags (Repo + Stack on every resource)
  modules/
    api-function/               Lambda + function URL + log group + least-privilege role
    front-door/cloudfront/      CloudFront + WAF on the CloudFront Free flat-rate plan
    circuit-breaker/            alarms + a Lambda that stops the function if it's overused
  live/prod/
    api-function/               the deployed function
    front-door/                 the public entry point (uses api-function's outputs)
    circuit-breaker/            watches api-function; re-apply api-function to reset it
```

The function only answers requests carrying the origin secret, which only the front door
sends. To try a different front door (e.g. API Gateway), add a module under
`modules/front-door/` that takes the same inputs (`origin_domain`, `origin_secret`) and
point `live/prod/front-door` at it.

Deploy:

```bash
./scripts/build-lambda.sh                       # dist/lambda.zip
cd infra/terragrunt/live/prod/api-function && terragrunt apply
cd ../front-door && terragrunt apply              # only when the front door changes
```
