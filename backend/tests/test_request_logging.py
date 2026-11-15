import logging

from fastapi.testclient import TestClient

from app import main


def test_request_logging_records_safe_fields_for_success_handled_error_and_exception(
    monkeypatch, caplog
):
    async def idle_scheduler(stop_event):
        await stop_event.wait()

    async def fail_request():
        raise RuntimeError("exception-detail-marker")

    monkeypatch.setattr(main, "reminder_scheduler", idle_scheduler)
    original_routes = list(main.app.router.routes)
    main.app.add_api_route(
        "/__test__/request-logging-failure",
        fail_request,
        methods=["POST"],
        include_in_schema=False,
    )
    caplog.set_level(logging.INFO, logger="app.main")

    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            success = client.get("/health")
            handled_error = client.get("/missing?query-detail-marker=hidden")
            unhandled_error = client.post(
                "/__test__/request-logging-failure?query-detail-marker=hidden",
                json={"body-detail-marker": "hidden"},
                headers={"Authorization": "Bearer header-detail-marker"},
            )

        assert success.status_code == 200
        assert handled_error.status_code == 404
        assert unhandled_error.status_code == 500
    finally:
        main.app.router.routes[:] = original_routes

    application_logs = "\n".join(
        record.getMessage() for record in caplog.records if record.name == "app.main"
    )
    assert "HTTP method=GET path=/health status=200 elapsed_ms=" in application_logs
    assert "HTTP method=GET path=/missing status=404 elapsed_ms=" in application_logs
    assert (
        "HTTP method=POST path=/__test__/request-logging-failure "
        "status=500 elapsed_ms="
    ) in application_logs
    assert all(
        marker not in application_logs
        for marker in (
            "query-detail-marker",
            "body-detail-marker",
            "header-detail-marker",
            "exception-detail-marker",
        )
    )
