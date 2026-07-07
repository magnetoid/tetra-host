"""GraphQL surface (/graphql) — token-authed parity with /api/v1."""


def _token(client) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "supersecurepassword"},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_graphql_requires_auth(client):
    response = client.post(
        "/graphql", json={"query": "{ dashboard { metrics { projects } } }"}
    )
    # Transport succeeds; the resolver rejects the unauthenticated query.
    assert response.status_code == 200
    body = response.json()
    assert body.get("errors"), body
    assert "Authentication required" in body["errors"][0]["message"]


def test_graphql_dashboard_and_projects(client):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    query = """
      {
        dashboard {
          metrics { projects unhealthyProjects mailDomains dnsZones admins }
          providers { name status }
        }
        projects { id name }
      }
    """
    response = client.post("/graphql", json={"query": query}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("errors"), body
    data = body["data"]
    assert isinstance(data["dashboard"]["metrics"]["admins"], int)
    assert data["dashboard"]["metrics"]["admins"] >= 1  # the bootstrap admin
    assert {p["name"] for p in data["dashboard"]["providers"]} >= {"Coolify", "Mailcow", "Cloudflare"}
    assert isinstance(data["projects"], list)
