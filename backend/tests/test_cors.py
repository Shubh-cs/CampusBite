from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_frontend_origin_can_send_authenticated_api_requests():
    origin = settings.frontend_origin

    with TestClient(app) as client:
        response = client.options(
            "/auth/me",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
