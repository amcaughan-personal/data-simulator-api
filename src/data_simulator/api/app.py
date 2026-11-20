"""HTTP API. Interactive docs are served at /docs."""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from data_simulator.api.csv_output import to_csv, wants_csv
from data_simulator.api.examples import DATASET_EXAMPLES
from data_simulator.engine import GenerationError, generate
from data_simulator.settings import Settings, load_settings
from data_simulator.spec import DatasetSpec

DESCRIPTION = """
Describe a dataset in a few lines of JSON and get realistic synthetic rows back.

- **Rows** can be independent records, one row per entity (users, institutions),
  events at random times, or regular time series, optionally one series per entity.
- **Columns** draw from distributions, depend on earlier columns through effects,
  and get noise and missing values.
- **Seeded**: the same spec and seed always return the same data.

Open `POST /v1/datasets`, choose an example and press *Try it out*.
Send `Accept: text/csv` to get CSV instead of JSON.
"""


class Dataset(BaseModel):
    name: str
    description: str | None
    seed: int
    row_count: int
    columns: list[str]
    rows: list[dict[str, Any]]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(
        title="Data Simulator API",
        version="1.0.0",
        description=DESCRIPTION,
        root_path=settings.root_path,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Say where and why, without echoing the submitted value back (which may not even
        # be valid JSON, e.g. NaN).
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    if settings.origin_secret:

        @app.middleware("http")
        async def require_origin_secret(request: Request, call_next):
            supplied = request.headers.get("x-origin-verify", "")
            if not hmac.compare_digest(supplied.encode(), settings.origin_secret.encode()):
                return JSONResponse({"detail": "Forbidden"}, status_code=403)
            return await call_next(request)

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url=f"{settings.root_path}/docs")

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/datasets",
        tags=["datasets"],
        summary="Generate a dataset from a spec",
        responses={
            200: {"content": {"text/csv": {}}, "description": "JSON by default; CSV with Accept: text/csv"}
        },
    )
    def create_dataset(
        spec: Annotated[DatasetSpec, Body(openapi_examples=DATASET_EXAMPLES)],
        accept: Annotated[str, Header()] = "application/json",
    ) -> Dataset:
        try:
            dataset = generate(spec, max_cells=settings.max_cells)
        except GenerationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        if wants_csv(accept):
            # CSV has nowhere to put metadata, so the seed and row count travel as headers.
            return Response(
                content=to_csv(dataset),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="{dataset["name"]}.csv"',
                    "X-Seed": str(dataset["seed"]),
                    "X-Row-Count": str(dataset["row_count"]),
                },
            )
        return Dataset(**dataset)

    return app


app = create_app()
