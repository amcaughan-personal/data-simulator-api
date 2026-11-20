"""HTTP API. Interactive docs are served at /docs."""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from data_simulator.api.csv_output import to_csv, wants_csv
from data_simulator.api.examples import DATASET_EXAMPLES, STREAM_EXAMPLES
from data_simulator.engine import GenerationError, generate, generate_window
from data_simulator.settings import Settings, load_settings
from data_simulator.simple import simple_spec
from data_simulator.spec import DatasetSpec, StreamWindowRequest

DESCRIPTION = """
Describe a dataset in a few lines of JSON and get realistic synthetic rows back.

- **Rows** can be independent records, one row per entity (users, institutions),
  events at random times, or regular time series, optionally one series per entity.
- **Columns** draw from distributions, depend on earlier columns through effects,
  and get noise and missing values.
- **Seeded**: the same spec and seed always return the same data.

Two endpoints:

- `POST /v1/datasets` returns one complete dataset.
- `POST /v1/streams/window` returns one time window of an endless stream. Every window
  is consistent with every other, so a pipeline can fetch hour after hour.
- `GET /v1/datasets/simple?rows=100&columns=5` returns plain data of that shape, for
  testing a pipeline without designing a data model.

Open either, choose an example and press *Try it out*.
Send `Accept: text/csv` to get CSV instead of JSON.
"""


class Dataset(BaseModel):
    name: str
    description: str | None
    seed: int
    row_count: int
    columns: list[str]
    rows: list[dict[str, Any]]


class StreamWindow(Dataset):
    start: str
    window: dict[str, str]


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

    # Specs are a few KB; anything this big is a mistake or abuse. (The CloudFront Free
    # plan can't enforce body size in WAF, so the app does.)
    max_body_bytes = 64 * 1024

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        declared = request.headers.get("content-length")
        too_big = int(declared) > max_body_bytes if declared and declared.isdigit() else False
        if not too_big and request.method in ("POST", "PUT", "PATCH"):
            too_big = len(await request.body()) > max_body_bytes
        if too_big:
            return JSONResponse({"detail": f"Request body over {max_body_bytes} bytes"}, status_code=413)
        return await call_next(request)

    # Lets web pages call the API from any site; it's public and uses no cookies.
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"], max_age=600
    )

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
        return _csv_response(dataset) if wants_csv(accept) else Dataset(**dataset)

    @app.get(
        "/v1/datasets/simple",
        tags=["datasets"],
        summary="Plain data of a given shape",
        responses={
            200: {"content": {"text/csv": {}}, "description": "JSON by default; CSV with Accept: text/csv"}
        },
    )
    def simple_dataset(
        rows: Annotated[int, Query(ge=1, le=100_000)] = 100,
        columns: Annotated[int, Query(ge=1, le=100, description="Including the id column.")] = 5,
        seed: Annotated[int | None, Query(ge=0)] = None,
        accept: Annotated[str, Header()] = "application/json",
    ) -> Dataset:
        """`id`, then columns cycling through a decimal, a whole number and a category."""
        try:
            dataset = generate(simple_spec(rows, columns, seed), max_cells=settings.max_cells)
        except GenerationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _csv_response(dataset) if wants_csv(accept) else Dataset(**dataset)

    @app.post(
        "/v1/streams/window",
        tags=["streams"],
        summary="Get one time window of an endless stream",
        responses={
            200: {"content": {"text/csv": {}}, "description": "JSON by default; CSV with Accept: text/csv"}
        },
    )
    def stream_window(
        request: Annotated[StreamWindowRequest, Body(openapi_examples=STREAM_EXAMPLES)],
        accept: Annotated[str, Header()] = "application/json",
    ) -> StreamWindow:
        """Same stream and seed, same rows: windows join up exactly, and individuals keep
        their fixed values across windows."""
        try:
            window = generate_window(request.stream, request.window, max_cells=settings.max_cells)
        except GenerationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return _csv_response(window) if wants_csv(accept) else StreamWindow(**window)

    return app


def _csv_response(data: dict[str, Any]) -> Response:
    # CSV has nowhere to put metadata, so the seed and row count travel as headers.
    return Response(
        content=to_csv(data),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{data["name"]}.csv"',
            "X-Seed": str(data["seed"]),
            "X-Row-Count": str(data["row_count"]),
        },
    )


app = create_app()
