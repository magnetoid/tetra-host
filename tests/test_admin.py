import re


def extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_admin_page_renders_for_authenticated_admin(authenticated_client):
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert "Admin Controls · Cloud Industry" in response.text
    assert "Admin Controls" in response.text
    assert "Provider readiness" in response.text


def test_mail_and_dns_pages_render_for_authenticated_admin(authenticated_client):
    mail_response = authenticated_client.get("/mail")
    dns_response = authenticated_client.get("/dns")
    assert mail_response.status_code == 200
    assert dns_response.status_code == 200
    assert "Mail Operations" in mail_response.text
    assert "DNS Operations" in dns_response.text


def test_admin_page_supports_tenant_creation(authenticated_client):
    page = authenticated_client.get("/admin")
    csrf_token = extract_csrf_token(page.text)

    response = authenticated_client.post(
        "/admin/tenants",
        data={
            "name": "Acme Hosting",
            "slug": "acme-hosting",
            "csrf_token": csrf_token,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Acme Hosting" in response.text
    assert "acme-hosting" in response.text


def test_admin_page_supports_tenant_admin_creation(authenticated_client):
    page = authenticated_client.get("/admin")
    csrf_token = extract_csrf_token(page.text)
    tenant_response = authenticated_client.post(
        "/admin/tenants",
        data={
            "name": "Beta Tenant",
            "slug": "beta",
            "csrf_token": csrf_token,
        },
        follow_redirects=True,
    )
    assert tenant_response.status_code == 200

    page = authenticated_client.get("/admin")
    csrf_token = extract_csrf_token(page.text)
    response = authenticated_client.post(
        "/admin/admins",
        data={
            "tenant_slug": "beta",
            "email": "owner@beta.test",
            "full_name": "Beta Owner",
            "password": "beta-password",
            "csrf_token": csrf_token,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "owner@beta.test" in response.text
    assert "Beta Tenant" in response.text


def test_admin_page_supports_resource_assignment(authenticated_client):
    page = authenticated_client.get("/admin")
    csrf_token = extract_csrf_token(page.text)
    tenant_response = authenticated_client.post(
        "/admin/tenants",
        data={
            "name": "Gamma Tenant",
            "slug": "gamma",
            "csrf_token": csrf_token,
        },
        follow_redirects=True,
    )
    assert tenant_response.status_code == 200

    page = authenticated_client.get("/admin")
    csrf_token = extract_csrf_token(page.text)
    response = authenticated_client.post(
        "/admin/resources",
        data={
            "tenant_slug": "gamma",
            "provider": "coolify",
            "resource_type": "site",
            "external_id": "app-gamma",
            "display_name": "Gamma App",
            "csrf_token": csrf_token,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Gamma App" in response.text
    assert "coolify · site" in response.text


def test_admin_page_lists_all_tenants_and_supports_deactivation(authenticated_client):
    page = authenticated_client.get("/admin")
    csrf_token = extract_csrf_token(page.text)
    create_response = authenticated_client.post(
        "/admin/tenants",
        data={
            "name": "Delta Tenant",
            "slug": "delta",
            "csrf_token": csrf_token,
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert "Delta Tenant" in create_response.text

    page = authenticated_client.get("/admin")
    csrf_token = extract_csrf_token(page.text)
    deactivate_response = authenticated_client.post(
        "/admin/tenants/delta/deactivate",
        data={"csrf_token": csrf_token},
        follow_redirects=True,
    )
    assert deactivate_response.status_code == 200
    assert "Inactive" in deactivate_response.text

    page = authenticated_client.get("/admin")
    csrf_token = extract_csrf_token(page.text)
    reactivate_response = authenticated_client.post(
        "/admin/tenants/delta/activate",
        data={"csrf_token": csrf_token},
        follow_redirects=True,
    )
    assert reactivate_response.status_code == 200
    assert "Active" in reactivate_response.text
