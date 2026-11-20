#!/usr/bin/env bash
# Build site/: a static API reference (Swagger UI + openapi.json) for GitHub Pages, so the
# reference stays up even when the API isn't. "Try it out" calls the live API.
set -euo pipefail

cd "$(dirname "$0")/.."
live_api_url="${LIVE_API_URL:-https://d1dfbd1pkurhz5.cloudfront.net}"

rm -rf site
mkdir -p site
cp scripts/docs-site/index.html site/

LIVE_API_URL="$live_api_url" uv run python - <<'PY'
import json, os
from data_simulator.api.app import create_app

schema = create_app().openapi()
schema["servers"] = [{"url": os.environ["LIVE_API_URL"], "description": "Live API"}]
with open("site/openapi.json", "w") as fh:
    json.dump(schema, fh, indent=2)
PY

echo "built site/ ($(ls site | tr '\n' ' '))"
