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
    deployment/                 CodeDeploy (canary + rollback) and the role CI deploys as
  live/
    prod/                       production; env.hcl holds its names and limits
      api-function/             the function and its live alias
      front-door/               the public entry point (uses api-function's outputs)
      circuit-breaker/          watches api-function; re-apply api-function to reset it
      deployment/               how code reaches the live alias
    staging/                    the same stacks, with staging's env.hcl
```

The function only answers requests carrying the origin secret, which only the front door
sends. To try a different front door (e.g. API Gateway), add a module under
`modules/front-door/` that takes the same inputs (`origin_domain`, `origin_secret`) and
point each environment's `front-door` stack at it.

Code is deployed by the deploy workflow (staging, then a production canary); this tree is
for infrastructure changes, applied staging first. See [docs/aws.md](../docs/aws.md).
