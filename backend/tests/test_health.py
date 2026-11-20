from conftest import FIXTURES, MakeClient
from fastapi.testclient import TestClient

from app.settings import Settings


def test_the_error_check_is_closed_without_its_key(client: TestClient) -> None:
    assert client.get("/api/health/error").status_code == 404
    assert client.get("/api/health/error", params={"key": "guess"}).status_code == 404


def test_the_error_check_raises_with_its_key(make_client: MakeClient) -> None:
    settings = Settings(
        _env_file=None,
        sign_in="fake",
        error_check_key="k",
        content_dir=str(FIXTURES / "content"),
    )
    client = make_client(settings=settings)
    client = type(client)(client.app, raise_server_exceptions=False)

    assert client.get("/api/health/error", params={"key": "k"}).status_code == 500


def test_every_response_says_which_revision_answered(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Revision"] == response.json()["revision"]
