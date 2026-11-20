"""AWS Lambda entry point: adapts API Gateway events to the FastAPI app."""

from mangum import Mangum

from data_simulator.api.app import app

handler = Mangum(app, lifespan="off")
