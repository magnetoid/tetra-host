"""Coolify compose → Tetra Engine stack rewrite (pure, no Docker)."""

import pytest
import yaml

from app.modules.importers.compose import (
    ComposeImportError,
    build_stack,
    detect_background,
    interpolate,
    parse_env_file,
)

UUID = "mxj8c7uxjb48rc3lixgdemeb"
SRC = f"/data/coolify/applications/{UUID}"
FILES = "/opt/tetra-host/data/stacks/mtio/files"

# Shaped like the real Coolify-rendered compose for a Supabase-backed site.
SOURCE = f"""
services:
  mtio-web:
    build:
      context: ./mtiosavljevic-web
      args:
        VITE_SUPABASE_URL: ${{VITE_SUPABASE_URL}}
    image: {UUID}_mtio-web:abc123
    container_name: mtio-web-{UUID}-1111
    restart: unless-stopped
    ports:
      - '127.0.0.1:${{APP_PORT:-9140}}:80'
    env_file: .env
    environment:
      NODE_ENV: production
      VITE_SUPABASE_URL: ${{VITE_SUPABASE_URL}}
      SERVICE_NAME_MTIO_MAILER: mtio-mailer
    depends_on:
      mtio-db:
        condition: service_healthy
    networks:
      mtio-net: null
      {UUID}: null
    labels:
      - coolify.managed=true
      - traefik.enable=true
      - caddy_0.encode=zstd gzip
      - com.example.keep=yes
  mtio-mailer:
    build: ./services/contact-mailer
    image: {UUID}_mtio-mailer:abc123
    container_name: mtio-mailer-{UUID}-2222
    env_file: .env
    environment:
      SUPABASE_URL: http://mtio-kong-{UUID}-4444:8000
    depends_on:
      mtio-db:
        condition: service_healthy
    networks:
      mtio-net: null
      {UUID}: null
  mtio-db:
    image: supabase/postgres:15.1.0.147
    container_name: mtio-db-{UUID}-3333
    ports:
      - '127.0.0.1:${{POSTGRES_PORT:-9146}}:5432'
    environment:
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
    volumes:
      - '{UUID}_mtio-postgres-data:/var/lib/postgresql/data'
      - '{SRC}/init.sql:/docker-entrypoint-initdb.d/init.sql:ro'
    networks:
      mtio-net: null
      {UUID}: null
  mtio-kong:
    image: kong:2.8.1
    container_name: mtio-kong-{UUID}-4444
    ports:
      - '127.0.0.1:${{KONG_HTTP_PORT:-9141}}:8000'
    volumes:
      - '{SRC}/scripts/kong.yml:/var/lib/kong/kong.yml:ro'
    depends_on:
      - mtio-db
    networks:
      - mtio-net
      - {UUID}
volumes:
  mtio-postgres-data:
    external: true
  {UUID}_mtio-postgres-data:
    name: {UUID}_mtio-postgres-data
networks:
  mtio-net:
    driver: bridge
  {UUID}:
    name: {UUID}
    external: true
"""

ENV = """
# comment
VITE_SUPABASE_URL=https://supabase.example.com
POSTGRES_PASSWORD='p@ss$word'
export SMTP_HOST=mail.example.com
QUOTED="line1\\nline2"
"""


def _build(**kwargs):
    defaults = dict(source_project=UUID, source_dir=SRC, project="mtio", files_dir=FILES)
    defaults.update(kwargs)
    text, plan = build_stack(SOURCE, ENV, **defaults)
    return yaml.safe_load(text), text, plan


def test_parse_env_file_handles_quotes_export_and_comments():
    env = parse_env_file(ENV + "INLINE=value # trailing\nBAD LINE\n")
    assert env["VITE_SUPABASE_URL"] == "https://supabase.example.com"
    assert env["POSTGRES_PASSWORD"] == "p@ss$word"
    assert env["SMTP_HOST"] == "mail.example.com"
    assert env["QUOTED"] == "line1\nline2"
    assert env["INLINE"] == "value"
    assert "BAD LINE" not in env


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("${A}", "a"),
        ("$A-x", "a-x"),
        ("${MISSING:-def}", "def"),
        ("${EMPTY:-def}", "def"),
        ("${EMPTY-def}", ""),
        ("${A:+alt}", "alt"),
        ("${MISSING+alt}", ""),
        ("${MISSING:-${A}}", "a"),
        ("cost $$5", "cost $5"),
        ("plain", "plain"),
    ],
)
def test_interpolate(text, expected):
    assert interpolate(text, {"A": "a", "EMPTY": ""}) == expected


def test_interpolate_required_and_missing_tracking():
    missing: set[str] = set()
    assert interpolate("${NOPE}", {}, missing) == ""
    assert missing == {"NOPE"}
    with pytest.raises(ComposeImportError):
        interpolate("${NOPE:?must be set}", {})


def test_strips_coolify_artifacts_and_resolves_ports():
    doc, _, plan = _build()
    web = doc["services"]["mtio-web"]
    assert "build" not in web and "container_name" not in web
    assert web["image"] == f"{UUID}_mtio-web:abc123"
    assert web["labels"] == ["com.example.keep=yes"]
    assert web["networks"] == {"mtio-net": None}
    assert web["ports"] == ["127.0.0.1:9140:80"]
    assert doc["networks"] == {"mtio-net": {"driver": "bridge"}}
    assert plan.locally_built == {
        "mtio-web": f"{UUID}_mtio-web:abc123",
        "mtio-mailer": f"{UUID}_mtio-mailer:abc123",
    }
    assert {(p.service, p.host_port) for p in plan.ports} == {
        ("mtio-web", 9140), ("mtio-db", 9146), ("mtio-kong", 9141)
    }


def test_env_file_is_folded_into_environment_with_environment_winning():
    doc, _, _ = _build()
    web_env = doc["services"]["mtio-web"]["environment"]
    assert web_env["NODE_ENV"] == "production"
    assert web_env["SMTP_HOST"] == "mail.example.com"  # from .env
    assert web_env["VITE_SUPABASE_URL"] == "https://supabase.example.com"
    assert "env_file" not in doc["services"]["mtio-web"]


def test_literal_dollar_is_escaped_for_compose():
    doc, text, _ = _build()
    # The YAML handed to compose must carry $$ so compose yields the literal value.
    assert doc["services"]["mtio-db"]["environment"]["POSTGRES_PASSWORD"] == "p@ss$$word"
    assert "${" not in text


def test_volumes_are_renamed_and_unused_external_dropped():
    doc, _, plan = _build()
    db = doc["services"]["mtio-db"]
    assert db["volumes"][0] == "mtio-postgres-data:/var/lib/postgresql/data"
    assert doc["volumes"] == {"mtio-postgres-data": {"name": "mtio_mtio-postgres-data"}}
    assert [(v.source_name, v.target_name) for v in plan.volumes] == [
        (f"{UUID}_mtio-postgres-data", "mtio_mtio-postgres-data")
    ]


def test_bind_mounts_move_to_files_dir():
    doc, _, plan = _build()
    assert doc["services"]["mtio-db"]["volumes"][1] == (
        f"{FILES}/init.sql:/docker-entrypoint-initdb.d/init.sql:ro"
    )
    assert sorted(b.rel_path for b in plan.binds) == ["init.sql", "scripts/kong.yml"]


def test_container_name_references_become_service_names():
    doc, _, _ = _build()
    assert doc["services"]["mtio-mailer"]["environment"]["SUPABASE_URL"] == "http://mtio-kong:8000"


def test_background_detection_ignores_coolify_service_vars():
    services = yaml.safe_load(SOURCE)["services"]
    assert detect_background(services) == ["mtio-mailer"]


def test_trial_copy_shifts_ports_and_drops_excluded_services():
    doc, _, plan = _build(project="mtio-staging", port_offset=10000, exclude=["mtio-mailer"])
    assert "mtio-mailer" not in doc["services"]
    assert doc["services"]["mtio-web"]["ports"] == ["127.0.0.1:19140:80"]
    assert doc["volumes"] == {"mtio-postgres-data": {"name": "mtio-staging_mtio-postgres-data"}}
    assert plan.excluded == ["mtio-mailer"]


def test_image_overrides_pin_imported_tags():
    doc, _, plan = _build(image_overrides={"mtio-web": "mtio-mtio-web:imported-abc123"})
    assert doc["services"]["mtio-web"]["image"] == "mtio-mtio-web:imported-abc123"
    assert plan.images["mtio-web"] == "mtio-mtio-web:imported-abc123"


def test_unknown_exclude_and_foreign_env_file_are_rejected():
    with pytest.raises(ComposeImportError):
        _build(exclude=["nope"])
    bad = SOURCE.replace("env_file: .env", "env_file: /etc/secret.env", 1)
    with pytest.raises(ComposeImportError):
        build_stack(bad, ENV, source_project=UUID, source_dir=SRC, project="x", files_dir=FILES)


def test_warnings_flag_dollar_values_and_public_ports():
    source = SOURCE.replace("'127.0.0.1:${KONG_HTTP_PORT:-9141}:8000'", "'9141:8000'")
    _, plan = build_stack(source, ENV, source_project=UUID, source_dir=SRC, project="x", files_dir=FILES)
    joined = " ".join(plan.warnings)
    assert "POSTGRES_PASSWORD" in joined
    assert "all interfaces" in joined
