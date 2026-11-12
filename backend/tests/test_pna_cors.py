def test_private_network_access_preflight(client):
    res = client.options(
        "/api/health",
        headers={
            "Origin": "https://urosnap.example.workers.dev",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Private-Network": "true",
        },
    )
    assert res.status_code in {200, 204}
    assert res.headers.get("access-control-allow-private-network") == "true"
    assert res.headers.get("access-control-allow-origin") in {"*", "https://urosnap.example.workers.dev"}


def test_health_includes_private_network_header(client):
    res = client.get("/api/health", headers={"Origin": "https://urosnap.example.workers.dev"})
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-private-network") == "true"
