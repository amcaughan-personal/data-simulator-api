# Design decisions

Why the API is built the way it is, and what each choice gives up.

- [The spec is organised around profiles](#the-spec-is-organised-around-profiles)
- [Statistical vocabulary, simple mechanics](#statistical-vocabulary-simple-mechanics)
- [Streams get their own endpoint](#streams-get-their-own-endpoint)
- [Streams are cut into fixed buckets](#streams-are-cut-into-fixed-buckets)
- [POST, even for reads](#post-even-for-reads)
- [Validate everything up front; never execute input](#validate-everything-up-front-never-execute-input)
- [Limit responses by cells, not rows](#limit-responses-by-cells-not-rows)
- [CloudFront in front, not API Gateway (for now)](#cloudfront-in-front-not-api-gateway-for-now)
- [An origin secret instead of IAM auth on the function URL](#an-origin-secret-instead-of-iam-auth-on-the-function-url)
- [A circuit breaker that needs a human to reset](#a-circuit-breaker-that-needs-a-human-to-reset)
- [Staging, versions and a canary](#staging-versions-and-a-canary)
- [CI ships code and applies infrastructure, but never deletes](#ci-ships-code-and-applies-infrastructure-but-never-deletes)
- [No API keys](#no-api-keys)
- [Staging, but no dev environment](#staging-but-no-dev-environment)
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

## Streams get their own endpoint

**Decision:** `POST /v1/datasets` returns a complete dataset; `POST /v1/streams/window` returns a window of an endless stream. They share profiles, columns and validation, but have separate request models.

**Why:** they promise different things. A dataset is finite and fully defined by its spec. A stream is pulled repeatedly, and every window must agree with every other, so the spec describes the stream and the window is a separate, per-call parameter. Separate models make each one validate exactly what applies (`count` on a stream is an error) and keep the docs precise. Shapes of data (records, events, series per individual) stay options of `rows`, because they combine; separate endpoints for them would duplicate everything else.

## Streams are cut into fixed buckets

**Decision:** a stream is divided into time buckets counted from its `start`. Each bucket is generated from the seed and the bucket's number, never from the window asked for; a window generates the buckets it touches and keeps the rows inside it. Bucket sizes come from the spec (about 1,000 rows each).

**Why:** that is what makes any two windows consistent, whatever their boundaries, and it's directly testable (the tests check that three arbitrary windows join up into the whole). Values fixed per individual use the stream seed rather than the bucket's, so they agree across windows. Row numbers count every earlier bucket's rows; bucket sizes are drawn 1,024 at a time, so even ten years in this takes a fraction of a second.

**Trade-off:** `random_walk` noise is not supported in streams, since a value would depend on every step since the start.

## POST, even for reads

**Decision:** both endpoints are `POST`, although they only read: nothing is stored, and the same request gives the same response.

The exception is `GET /v1/datasets/simple`, whose input is just a few numbers.

**Why:** the spec is structured JSON of up to 64 KB. `GET` has no standard request body (CloudFront and many clients drop it), and squeezing specs into query strings would be unreadable and hit URL length limits. This is the usual choice for query-style APIs (Elasticsearch's search, GraphQL).

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

**What testing showed:** API Gateway doesn't bill rejected requests. A throwaway REST API received 4,706 requests in batches sized so the bill would show which kinds count: only the 194 successful ones were billed, and the 403s (missing or invalid API key) and 429s (throttling and usage-plan quotas) were free. So API Gateway with throttling and quotas would also give a bounded cost, and it's a candidate front door. Switching would be a change to the front-door stack alone, which is kept separate for that reason.

**Trade-offs found by testing the Free plan:** it allows up to 5 WAF rules, but rejects custom block responses, body-size rules and method matching. So rate-limited clients get WAF's default `403` rather than a `429`, and the app enforces the body limit (`413`) and methods (`405`) itself.

## An origin secret instead of IAM auth on the function URL

**Decision:** the function URL has no IAM auth. CloudFront adds a secret header, and the app rejects requests without it.

**Why:** CloudFront's built-in protection for Lambda origins (origin access control) requires clients to send a SHA-256 of every POST body, unusable for a public JSON API. The standard workaround computes it in Lambda@Edge, which is billed per request outside the flat-rate plan and would bring back the unbounded cost.

**Trade-off:** someone who learned the (unpublished) function URL could call it directly, skipping WAF. Those calls are rejected in about a millisecond, and the concurrency cap still applies.

## A circuit breaker that needs a human to reset

**Decision:** two CloudWatch alarms watch the function's invocations (more than 1,000 in 5 minutes, or more than 20,000 in a day). Either one triggers a small Lambda that sets the API function's reserved concurrency to 0, and emails. Turning it back on means re-applying the function stack.

**Why:** WAF limits each IP, but many IPs together (or a leaked function URL) could still keep the function busy. The concurrency cap already bounds the rate; the breaker bounds the total. Stopping is automatic because attacks happen at night; restarting is manual because someone should look first. The breaker's role can change concurrency on that one function and nothing else.

**Trade-off:** a genuine traffic spike also takes the API offline until someone resets it. For a demo that's the right way round.

## Staging, versions and a canary

**Decision:** two identical environments (the same stacks, with a per-environment
`env.hcl`). Each deploy publishes an immutable Lambda version, and CodeDeploy moves a `live`
alias to it: all at once in staging, and as a 10%-for-5-minutes canary in production that
rolls back if the alias's error alarm fires. Production also waits for an approval.

**Why:** it's the standard way to ship a service safely, at no real cost: staging's
CloudFront is on its own Free plan, and idle Lambda costs nothing. CodeDeploy's built-in
Lambda canary is free and replaces what would otherwise be hand-written traffic-shifting
scripts. The approval lives in GitHub's environment settings, so dropping it (pure CI/CD)
is a one-line change in personal-infra, with no workflow change.

**Trade-off:** more moving parts than "terraform apply", and a merge takes about ten
minutes to reach production. Configuration changes take effect with the next deploy,
because a version keeps the configuration it was published with.

## CI ships code and applies infrastructure, but never deletes

**Decision:** the deploy workflow uploads code and moves the alias for one function.
Infrastructure changes are planned on the pull request and applied from `main` by CI,
staging first, prod after approval. CI's apply role can create and change this repo's
resources but not delete them; destroys, and the few things listed in
[AWS architecture](aws.md#changing-infrastructure), are applied by hand.

**Why:** a role that can apply Terraform could grant itself anything, so its limits come from
outside this repo. All of CI's roles are defined in personal-infra: the deploy roles, the
read-only plan role, and the apply role, which can act only on `data-simulator-api*` resources
(CloudFront distributions by their `Repo` tag) and can create roles only with a permissions
boundary capping them at this repo's logs, alias and throttle. A PR here can't widen any of
them. Deletes are where a mistake costs the most, so they keep a person in the loop.

## No API keys

**Decision:** the API is open, with no keys.

**Why:** a key published in the README for anyone to try protects nothing, and per-key quotas were an API Gateway feature. Per-IP rate limits, the concurrency cap and the cost bounds do that job.

## Staging, but no dev environment

**Decision:** two deployed environments, staging and production (see [above](#staging-versions-and-a-canary)). Development happens locally (`uvicorn`, `pytest`), not in a cloud dev environment.

**Why:** staging earns its place by testing the real deploy path (the package, the alias, CodeDeploy and the front door) before production sees it. A per-developer cloud environment wouldn't catch anything local runs and CI don't. Stacks are split both by role (function, front door, circuit breaker, deployment) and by environment, with an `env.hcl` holding the only differences.

## Small, reproducible build

**Decision:** Lambda on arm64 (Graviton, about 20% cheaper), packaged by a script that produces a byte-identical zip from unchanged code.

**Why:** deterministic builds mean Terraform only redeploys real changes, and the package is easy to reason about: the app plus runtime wheels, no dev tools. Building in the deploy step rather than inside Terraform keeps `terraform apply` free of side effects.

## Tests cover behaviour, not lines

**Decision:** about forty tests, one per promise the docs make (row shapes, profiles, effects, noise, anomalies, limits, error handling, the HTTP contract), rather than coverage targets.

**Why:** each test documents a behaviour someone relies on. A suite padded for coverage costs more to maintain than it catches.

## Security-scan exceptions live next to the code

**Decision:** Checkov exceptions specific to one resource are inline comments on that resource (`#checkov:skip=CHECK:reason`). The repo-wide skip file only holds decisions that apply everywhere.

**Why:** a global skip silently exempts *future* resources too. An inline skip records the reason where a reviewer will see it, and the check still runs on anything new.
