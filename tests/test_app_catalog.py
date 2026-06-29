import base64

import yaml

from app.services.app_catalog import (
    normalize_compose_for_engine,
    normalize_template,
    render_service_vars,
)


def test_normalize_compose_declares_implicit_named_volumes():
    compose = """
services:
  wordpress:
    image: wordpress:latest
    volumes:
      - 'wordpress-files:/var/www/html'
      - '/host/path:/bind'
  mariadb:
    image: mariadb:11
    volumes:
      - 'mariadb-data:/var/lib/mysql'
"""
    doc = yaml.safe_load(normalize_compose_for_engine(compose))
    assert "wordpress-files" in doc["volumes"]
    assert "mariadb-data" in doc["volumes"]
    assert "/host/path" not in doc["volumes"]  # bind mounts are not declared


def test_normalize_and_decode_compose():
    raw = base64.b64encode(b"services:\n  web: {}\n").decode()
    template = normalize_template(
        "wordpress-with-mysql",
        {
            "compose": raw,
            "slogan": "The famous blogging platform.",
            "category": "cms",
            "tags": ["cms", "blog"],
            "logo": "svgs/wordpress.svg",
            "port": "80",
        },
    )
    assert template.name == "Wordpress With Mysql"
    assert template.category == "cms"
    assert template.tags == ["cms", "blog"]
    assert "services:" in template.decoded_compose()


def test_render_service_vars_generates_each_kind():
    compose = """
    environment:
      WORDPRESS_DB_PASSWORD: ${SERVICE_PASSWORD_MYSQL}
      WORDPRESS_DB_USER: ${SERVICE_USER_MYSQL}
      - SERVICE_FQDN_WORDPRESS
      APP_KEY: ${SERVICE_BASE64_APPKEY}
      SITE_URL: ${SERVICE_URL_WORDPRESS}
    """
    env = render_service_vars(compose, domain="wp.example.com")

    assert env["SERVICE_FQDN_WORDPRESS"] == "wp.example.com"
    assert env["SERVICE_URL_WORDPRESS"] == "https://wp.example.com"
    assert len(env["SERVICE_PASSWORD_MYSQL"]) == 24
    assert env["SERVICE_USER_MYSQL"].isalnum()
    assert env["SERVICE_BASE64_APPKEY"]


def test_render_service_vars_long_password_and_dedup():
    env = render_service_vars(
        "${SERVICE_PASSWORD_64_DB} ${SERVICE_PASSWORD_64_DB}", domain=""
    )
    assert len(env) == 1  # same token -> one value
    assert len(env["SERVICE_PASSWORD_64_DB"]) == 64  # _64_ variant is long
