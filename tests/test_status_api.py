def test_status_is_public_and_reports_api(client):
    # No Authorization header — the status feed must be public.
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] in {"operational", "degraded", "down"}
    assert any(c["name"] == "Control plane API" for c in body["components"])
    assert body["updated_at"]
