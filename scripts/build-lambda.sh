#!/usr/bin/env bash
# Build dist/lambda.zip: the app plus its runtime dependencies (no dev tools), as Linux
# arm64 wheels for the Lambda Python 3.12 runtime.
#
# Files are added in sorted order with a fixed timestamp, so unchanged code produces a
# byte-identical zip and Terraform only redeploys when something actually changed.
set -euo pipefail

cd "$(dirname "$0")/.."
build_dir=build/lambda
zip_path=dist/lambda.zip

rm -rf "$build_dir" "$zip_path"
mkdir -p "$build_dir" dist

uv export --frozen --no-dev --no-emit-project --no-hashes --format requirements.txt --quiet \
  > build/requirements.txt
uv pip install --quiet \
  --target "$build_dir" \
  --python-version 3.12 \
  --python-platform aarch64-manylinux_2_28 \
  --only-binary :all: \
  -r build/requirements.txt

cp -r src/data_simulator "$build_dir/"
find "$build_dir" -name __pycache__ -type d -prune -exec rm -rf {} +

python3 - "$build_dir" "$zip_path" <<'PY'
import os, sys, zipfile
src, dest = sys.argv[1], sys.argv[2]
paths = sorted(os.path.relpath(os.path.join(d, f), src) for d, _, files in os.walk(src) for f in files)
with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for path in paths:
        info = zipfile.ZipInfo(path, date_time=(2000, 1, 1, 0, 0, 0))
        info.external_attr = 0o644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        with open(os.path.join(src, path), "rb") as fh:
            zf.writestr(info, fh.read())
PY

echo "built $zip_path ($(du -h "$zip_path" | cut -f1))"
