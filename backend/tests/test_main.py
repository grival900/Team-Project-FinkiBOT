from fastapi.testclient import TestClient

from backend.api.main import app


def test_unhandled_exception_still_carries_cors_headers():
    # without CORS headers the browser only shows "Failed to fetch"

    @app.get("/__test_boom")
    def boom():
        raise RuntimeError("deliberate test crash")

    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/__test_boom", headers={"Origin": "http://localhost:8080"})

        assert response.status_code == 500
        assert response.headers.get("access-control-allow-origin") == "http://localhost:8080"
        assert response.json() == {"detail": "Internal server error"}
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/__test_boom"]
