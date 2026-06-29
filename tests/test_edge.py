import yaml

from app.config import get_settings
from app.services.edge import apply_edge

WP_COMPOSE = """
services:
  wordpress:
    image: wordpress:latest
    environment:
      - SERVICE_FQDN_WORDPRESS
      - WORDPRESS_DB_HOST=mariadb
  mariadb:
    image: mariadb:11
"""


def test_apply_edge_is_noop_when_disabled():
    # Default config has edge_network="" -> edge disabled -> compose returned unchanged.
    assert apply_edge(WP_COMPOSE, project="blog", port="80") == WP_COMPOSE


def test_apply_edge_labels_only_the_public_service(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "edge_network", "tetra-edge")
    monkeypatch.setattr(settings, "apps_base_domain", "apps.example.com")

    doc = yaml.safe_load(apply_edge(WP_COMPOSE, project="blog", port="80"))

    wp = doc["services"]["wordpress"]
    assert wp["labels"]["caddy"] == "blog.apps.example.com"
    assert wp["labels"]["caddy.reverse_proxy"] == "{{upstreams 80}}"
    net = wp["networks"]
    assert "tetra-edge" in (net if isinstance(net, list) else net.keys())
    assert doc["networks"]["tetra-edge"] == {"external": True}

    # The DB service has no SERVICE_FQDN_ marker, so it must not be exposed.
    assert "labels" not in doc["services"]["mariadb"]
