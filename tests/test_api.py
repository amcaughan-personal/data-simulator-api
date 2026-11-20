import pytest
from fastapi.testclient import TestClient

from data_simulator.api.app import create_app
from data_simulator.api.examples import DATASET_EXAMPLES
from data_simulator.settings import Settings


@pytest.fixture
def client():
    return TestClient(create_app(Settings(max_rows=500, root_path="")))


@pytest.mark.parametrize("name", list(DATASET_EXAMPLES))
def test_docs_examples_work(client, name):
    response = client.post("/v1/datasets", json=DATASET_EXAMPLES[name]["value"])
    assert response.status_code == 200, response.text
    assert response.json()["row_count"] == len(response.json()["rows"])


def test_bad_requests_return_422_with_a_reason(client):
    columns = {"x": {"normal": {}}}
    invalid = client.post("/v1/datasets", json={"rows": {"one_each": True}, "common_columns": columns})
    assert invalid.status_code == 422 and "needs every profile to have a count" in invalid.text

    too_big = client.post("/v1/datasets", json={"rows": {"count": 501}, "common_columns": columns})
    assert too_big.status_code == 422 and "limit is 500" in too_big.text


def test_lambda_handler_serves_api_gateway_events():
    from data_simulator.lambda_handler import handler

    event = {
        "resource": "/{proxy+}",
        "path": "/health",
        "httpMethod": "GET",
        "headers": {"Host": "example.com"},
        "multiValueHeaders": {},
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "requestContext": {
            "resourcePath": "/{proxy+}",
            "httpMethod": "GET",
            "path": "/health",
            "stage": "test",
        },
        "body": None,
        "isBase64Encoded": False,
    }
    response = handler(event, None)
    assert response["statusCode"] == 200 and '"ok"' in response["body"]
