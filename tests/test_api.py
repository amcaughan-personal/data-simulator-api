import pytest
from fastapi.testclient import TestClient

from data_simulator.api.app import create_app
from data_simulator.api.examples import DATASET_EXAMPLES, INSTITUTIONS
from data_simulator.settings import Settings


@pytest.fixture
def client():
    return TestClient(create_app(Settings(max_rows=500, root_path="")))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_root_redirects_to_docs(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_openapi_lists_examples(client):
    schema = client.get("/openapi.json").json()
    body = schema["paths"]["/v1/datasets"]["post"]["requestBody"]["content"]["application/json"]
    assert set(body["examples"]) == set(DATASET_EXAMPLES)


@pytest.mark.parametrize("name", list(DATASET_EXAMPLES))
def test_docs_examples_work(client, name):
    response = client.post("/v1/datasets", json=DATASET_EXAMPLES[name]["value"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_count"] == len(body["rows"])


def test_invalid_spec_returns_422_with_reason(client):
    response = client.post("/v1/datasets", json={**INSTITUTIONS, "rows": {"one_per": "banks"}})
    assert response.status_code == 422
    assert "unknown entity 'banks'" in response.text


def test_row_limit_returns_422(client):
    response = client.post(
        "/v1/datasets", json={"rows": {"count": 501}, "columns": [{"name": "x", "type": "numeric"}]}
    )
    assert response.status_code == 422
    assert "limit is 500" in response.json()["detail"]


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
        "pathParameters": {"proxy": "health"},
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
    assert response["statusCode"] == 200
    assert '"ok"' in response["body"]
