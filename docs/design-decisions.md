# Design decisions

Why the API is built the way it is, and what each choice gives up.

- [The spec is organised around profiles](#the-spec-is-organised-around-profiles)
- [Statistical vocabulary, simple mechanics](#statistical-vocabulary-simple-mechanics)
- [Validate everything up front; never execute input](#validate-everything-up-front-never-execute-input)
- [Limit responses by cells, not rows](#limit-responses-by-cells-not-rows)
- [CloudFront in front, not API Gateway (for now)](#cloudfront-in-front-not-api-gateway-for-now)
- [An origin secret instead of IAM auth on the function URL](#an-origin-secret-instead-of-iam-auth-on-the-function-url)
- [A circuit breaker that needs a human to reset](#a-circuit-breaker-that-needs-a-human-to-reset)
- [No API keys](#no-api-keys)
- [One environment](#one-environment)
- [Small, reproducible build](#small-reproducible-build)
- [Tests cover behaviour, not lines](#tests-cover-behaviour-not-lines)
- [Security-scan exceptions live next to the code](#security-scan-exceptions-live-next-to-the-code)

## The spec is organised around profiles

**Decision:** a dataset is made of *profiles* (kinds of things, like standard and premium cards). Each profile declares the same columns, with its own distribution for each. `common_columns` hold anything shared.

**Why:** an earlier design spread one concept across three places (a list of entities, a row setting, and special column types) and expressed differences between kinds of things as rules ("multiply by 1.8 if premium"). Profiles say the same thing directly: *premium cards' amounts are lognormal with median 60*. Each profile reads on its own, the distributions can differ in shape and not just scale, and the profile column doubles as ground truth.

**Trade-off:** some repetition when profiles share most columns, which `common_columns` absorbs. Every profile must list the same columns (`null` for "always empty"), which catches typos instead of silently producing empty values.

## Statistical vocabulary, simple mechanics

**Decision:** columns are named by their distribution (`normal`, `lognormal`, `poisson`, `bernoulli`, ...). Adjustments are plain words (`trend`, `seasonality`, `multiply_column`, `noise`, `missing`).

**Why:** the audience includes data people, for whom "lognormal with median 35" is clearer than a home-made vocabulary. Earlier drafts tried plainer names and lost precision. Other choices keep the mechanics simple to read:
- probabilities must add up to 1 (not relative weights)
- IDs are just `name_0001`
- a column can only reference columns *above* it, so reference loops can't exist

**Trade-off:** some features were cut to keep this readable: scoped mutation rules, per-entity drift, template columns.

## Validate everything up front; never execute input

**Decision:** every request is validated by strict Pydantic models before any work happens. Unknown fields are rejected; names must match `^[A-Za-z_][A-Za-z0-9_]*$`; text, numbers and sizes are bounded; `NaN` and `Infinity` are refused. There's no `eval`, shell, file, network or templating code anywhere, so input only ever becomes data.

**Why:** with no code path that interprets input, there is nothing to escape into. Hostile inputs (code as names or values, path traversal, deep nesting, huge numbers and strings) were tested: each is either rejected with a clear `422` or returned as plain data. Validation errors say where and why without echoing the submitted value back.

**Backstop:** the Lambda role can only write its own logs, so even a hypothetical code-execution bug would have nothing to reach.

## Limit responses by cells, not rows

**Decision:** a request may produce at most 100,000 cells (rows × columns, about 3 MB of JSON), plus caps on columns, profiles, individuals and text length.

**Why:** a row limit alone let a 12 KB request ask for a 71 MB response (5,000 rows × 500 columns). Cells measure what actually costs memory, time and bandwidth, and 3 MB stays well under Lambda's 6 MB response limit.

## CloudFront in front, not API Gateway (for now)

**Decision:** the public entry point is CloudFront with WAF, on CloudFront's Free flat-rate plan.

**Why:** the requirement is that a flood of traffic can't run up a bill. API Gateway bills per request, and AWS's documentation doesn't say whether rejected requests (`403`, or `429` for throttling or quotas) are billed, so a worst-case estimate has to assume they are. CloudFront's flat-rate plan has no overage charges, includes WAF, and doesn't count requests WAF blocks against its allowance.

**Open question:** an experiment (4,706 requests to a throwaway API Gateway API, in batches sized so the bill reveals which kinds are billed) is waiting on Cost Explorer. If rejected requests turn out to be free, API Gateway with throttling becomes the preferred front door. The front door is a separate stack for exactly that reason.

**Trade-offs found by testing the Free plan:** it allows up to 5 WAF rules, but rejects custom block responses, body-size rules and method matching. So rate-limited clients get WAF's default `403` rather than a `429`, and the app enforces the body limit (`413`) and methods (`405`) itself.

## An origin secret instead of IAM auth on the function URL

**Decision:** the function URL has no IAM auth. CloudFront adds a secret header, and the app rejects requests without it.

**Why:** CloudFront's built-in protection for Lambda origins (origin access control) requires clients to send a SHA-256 of every POST body, unusable for a public JSON API. The standard workaround computes it in Lambda@Edge, which is billed per request outside the flat-rate plan and would bring back the unbounded cost.

**Trade-off:** someone who learned the (unpublished) function URL could call it directly, skipping WAF. Those calls are rejected in about a millisecond, and the concurrency cap still applies.

## A circuit breaker that needs a human to reset

**Decision:** two CloudWatch alarms watch the function's invocations (more than 1,000 in 5 minutes, or more than 20,000 in a day). Either one triggers a small Lambda that sets the API function's reserved concurrency to 0, and emails. Turning it back on means re-applying the function stack.

**Why:** WAF limits each IP, but many IPs together (or a leaked function URL) could still keep the function busy. The concurrency cap already bounds the rate; the breaker bounds the total. Stopping is automatic because attacks happen at night; restarting is manual because someone should look first. The breaker's role can change concurrency on that one function and nothing else.

**Trade-off:** a genuine traffic spike also takes the API offline until someone resets it. For a demo that's the right way round.

## No API keys

**Decision:** the API is open, with no keys.

**Why:** a key published in the README for anyone to try protects nothing, and per-key quotas were an API Gateway feature. Per-IP rate limits, the concurrency cap and the cost bounds do that job.

## One environment

**Decision:** one deployed environment (`live/prod`), with development done locally (`uvicorn`, `pytest`).

**Why:** for a small public demo, a second cloud environment would double the infrastructure without catching anything the local setup and CI don't. Splitting stacks by role (function and front door) rather than by environment turned out to be the more useful seam.

## Small, reproducible build

**Decision:** Lambda on arm64 (Graviton, about 20% cheaper), packaged by a script that produces a byte-identical zip from unchanged code.

**Why:** deterministic builds mean Terraform only redeploys real changes, and the package is easy to reason about: the app plus runtime wheels, no dev tools. Building in the deploy step rather than inside Terraform keeps `terraform apply` free of side effects.

## Tests cover behaviour, not lines

**Decision:** about forty tests, one per promise the docs make (row shapes, profiles, effects, noise, anomalies, limits, error handling, the HTTP contract), rather than coverage targets.

**Why:** each test documents a behaviour someone relies on. A suite padded for coverage costs more to maintain than it catches.

## Security-scan exceptions live next to the code

**Decision:** Checkov exceptions specific to one resource are inline comments on that resource (`#checkov:skip=CHECK:reason`). The repo-wide skip file only holds decisions that apply everywhere.

**Why:** a global skip silently exempts *future* resources too. An inline skip records the reason where a reviewer will see it, and the check still runs on anything new.
