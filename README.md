# data-simulator-api

Describe the kinds of things in your data and how each column is distributed; get realistic synthetic rows back.

**Try it:** https://d1dfbd1pkurhz5.cloudfront.net/docs, the interactive docs with runnable examples. A static copy of the API reference is also on [GitHub Pages](https://amcaughan-personal.github.io/data-simulator-api/), so it stays up even if the API is down.

```bash
curl -X POST https://d1dfbd1pkurhz5.cloudfront.net/v1/datasets \
  -H "Content-Type: application/json" \
  -d '{"seed": 1, "rows": {"count": 3},
       "common_columns": {"region": {"categorical": ["north", "south"]}, "orders": {"poisson": {"mean": 4}}}}'
```

```json
{"name": "dataset", "seed": 1, "row_count": 3, "columns": ["region", "orders"],
 "types": {"region": "string", "orders": "integer"},
 "rows": [{"region": "south", "orders": 5}, {"region": "north", "orders": 4}, {"region": "north", "orders": 3}]}
```

Just need rows to test a pipeline? `GET /v1/datasets/simple?rows=100&columns=5` returns plain data of that shape. Need a feed rather than a one-off table? `POST /v1/streams/window` treats a spec as an endless stream: fetch any time window, and consecutive windows join up exactly, so ELT jobs and dbt models can pull it hour by hour.

Datasets can mix several kinds of things (standard and premium cards, indoor and outdoor sensors), follow trends and daily or weekly cycles, include labelled anomalies, and come back as JSON or CSV. The same spec and seed always give the same data.

## Documentation

| Page | What's in it |
|---|---|
| [Using the API](docs/api.md) | The spec and every option, streams, CSV, limits and errors |
| [Examples](docs/examples.md) | Complete specs and the data they produce |
| [AWS architecture](docs/aws.md) | How it runs: CloudFront, WAF, Lambda, Terraform layout, cost controls, deploying |
| [Design decisions](docs/design-decisions.md) | Why it's built this way, and what was traded off |

## Run it locally

```bash
uv sync
uv run uvicorn data_simulator.api.app:app --reload   # http://127.0.0.1:8000/docs
uv run pytest
```

uv uses the Python version in `.python-version`. For infrastructure work, open the repo in
the dev container (VS Code: *Reopen in Container*): it has the AWS CLI and the Terraform,
Terragrunt and uv versions from `.tool-versions`. Without VS Code:

```bash
docker build -f .devcontainer/Dockerfile -t data-simulator-api-dev .
docker run --rm -it -v "$PWD:/workspace" -v "$HOME/.aws:/home/dev/.aws" data-simulator-api-dev
```

## Repository layout

```
src/data_simulator/
  spec.py              the spec: every option, validated (also drives /docs)
  engine/              rows.py → columns.py → output.py
  api/app.py           FastAPI app: GET /health, POST /v1/datasets
  lambda_handler.py    AWS Lambda entry point
tests/
infra/                 Terraform/Terragrunt for AWS
scripts/build-lambda.sh
docs/
```

## License

MIT
