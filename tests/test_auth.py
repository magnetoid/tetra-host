import re


def extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_login_rejects_invalid_credentials(client):
    login_page = client.get("/auth/login")
    assert login_page.headers["cache-control"] == "no-store"
    csrf_token = extract_csrf_token(login_page.text)
    response = client.post(
        "/auth/login",
        data={
            "email": "admin@example.com",
            "password": "wrong-password",
            "csrf_token": csrf_token,
            "next_url": "/dashboard",
        },
    )
    assert response.status_code == 401
    assert "Invalid credentials." in response.text


def test_login_and_logout_flow(client):
    login_page = client.get("/auth/login")
    csrf_token = extract_csrf_token(login_page.text)
    response = client.post(
        "/auth/login",
        data={
            "email": "admin@example.com",
            "password": "supersecurepassword",
            "csrf_token": csrf_token,
            "next_url": "/dashboard",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    assert client.cookies.get("tetra_host_session")

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Logout" in dashboard.text

    page_token = extract_csrf_token(dashboard.text)
    logout_response = client.post(
        "/auth/logout",
        data={"csrf_token": page_token},
        follow_redirects=False,
    )
    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/auth/login"
