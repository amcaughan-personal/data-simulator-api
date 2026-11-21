# How it's built

A short tour of the engineering around the API: how changes are checked, shipped and
watched, and what bounds its cost. Each section links to the details.

- [Every change is checked](#every-change-is-checked)
- [Shipping: staging, then a canary](#shipping-staging-then-a-canary)
- [Cost has a ceiling](#cost-has-a-ceiling)
- [Security](#security)
- [Monitoring](#monitoring)
- [Infrastructure as code](#infrastructure-as-code)
- [Development environment](#development-environment)

## Every change is checked

`main` only changes through pull requests, and these checks must pass first:

- **Python:** ruff (lint and format) and pytest, on the version in `.python-version`.
- **Infrastructure formatting:** `terraform fmt` and `terragrunt hcl format`, with the
  versions in `.tool-versions`.
- **Security scans:** Checkov (infrastructure code), Trivy (vulnerable dependencies),
  gitleaks (leaked secrets) and actionlint (workflow errors). A finding fails the PR; a
  comment lists the findings.

The checks are reusable workflows from
[shared-workflows](https://github.com/amcaughan-personal/shared-workflows), pinned to a
version. GitHub Actions, Docker images and Python packages are all pinned exactly, and
Dependabot proposes updates only once a release is a week old.

## Shipping: staging, then a canary

Every merge to `main` runs the [deploy workflow](../.github/workflows/deploy.yml):

1. Build the Lambda package once.
2. Deploy it to **staging** and run the smoke tests.
3. Deploy the same package to **production** as a **canary**: 10% of traffic for 5 minutes,
   then all of it. If the error alarm fires during the canary, CodeDeploy moves traffic
   back to the previous version on its own.
4. Smoke-test production.

Each deploy publishes an immutable Lambda version and moves a `live` alias, so rolling back
is re-running an earlier deploy. Production can also require an approval (a setting on the
GitHub environment). Details: [AWS architecture: how code is deployed](aws.md#how-code-is-deployed).

## Cost has a ceiling

The API is public, so its worst-case cost is bounded:

- CloudFront's Free flat-rate plan (WAF included) costs $0, with no overage charges.
- WAF rate-limits each IP and blocks known-bad IPs before requests reach the function.
- Reserved concurrency caps how many requests run at once; throttled requests aren't billed.
- A circuit breaker stops the function entirely after unusually high use, and emails.

Details: [AWS architecture: cost bounds](aws.md#cost-bounds).

## Security

- **No stored cloud credentials:** CI signs in to AWS through GitHub's OIDC provider, as a
  per-environment role that only that GitHub environment (main only) can assume, and that
  can deploy that one function and nothing else.
- **Least privilege:** the function can only write its own logs; the circuit breaker can only
  change the function's concurrency.
- **Closed origin:** the function URL rejects requests without a secret header that only
  CloudFront sends.
- **Input is data, never code:** specs are validated against strict models and limits before
  anything runs. See [design decisions](design-decisions.md#validate-everything-up-front-never-execute-input).

## Monitoring

- **Error alarm** on the `live` alias: failed invocations plus 5xx responses. It triggers the
  canary rollback during deploys, and emails in production.
- **Scheduled smoke test:** every 6 hours, the [smoke tests](../scripts/smoke-test.sh) run
  against production from GitHub Actions.
- **Circuit-breaker alarms** email when they trip.

## Infrastructure as code

Everything runs from Terraform, organised with Terragrunt into small stacks (function, front
door, circuit breaker, deployment) per environment, with an `env.hcl` holding the only
differences between staging and production. Changes are applied by hand from a reviewed plan;
CI ships code but can't change infrastructure. See [AWS architecture](aws.md#infrastructure-as-code).

## Development environment

The repo opens in a dev container (VS Code: *Reopen in Container*) with the same tool
versions CI uses, all read from `.tool-versions` and `.python-version`. The container's base
image comes from [dev-environment](https://github.com/amcaughan-personal/dev-environment).
