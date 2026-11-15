from fastapi.testclient import TestClient

from app import main
from app.core.config import settings


def test_frontend_origin_can_send_authenticated_api_requests(monkeypatch):
    origin = settings.frontend_origin
    scheduler_starts = []

    async def inert_scheduler(stop_event):
        scheduler_starts.append(True)
        await stop_event.wait()

    monkeypatch.setattr(main, "reminder_scheduler", inert_scheduler)

    with TestClient(main.app) as client:
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
    assert scheduler_starts == [True]
