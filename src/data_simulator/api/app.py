"""HTTP API. Interactive docs are served at /docs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

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

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url=f"{settings.root_path}/docs")

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/datasets", tags=["datasets"], summary="Generate a dataset from a spec")
    def create_dataset(spec: Annotated[DatasetSpec, Body(openapi_examples=DATASET_EXAMPLES)]) -> Dataset:
        try:
            return Dataset(**generate(spec, max_rows=settings.max_rows))
        except GenerationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return app


app = create_app()
