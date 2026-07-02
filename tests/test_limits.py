"""Container resource limits (cgroup v2 hard caps) injected into tenant stacks."""

import yaml

from app.services.limits import apply_resource_limits

_TWO_SERVICE = yaml.safe_dump(
    {
        "services": {
            "app": {"image": "wp", "environment": ["SERVICE_FQDN_APP=x"]},
            "db": {"image": "mariadb"},
        }
    },
    sort_keys=False,
)


def test_limits_applied_to_every_service():
    out = yaml.safe_load(
        apply_resource_limits(_TWO_SERVICE, cpu_millicores=1500, mem_mb=512, pids_limit=256)
    )
    for name in ("app", "db"):
        svc = out["services"][name]
        assert svc["cpus"] == 1.5
        assert svc["mem_limit"] == "512m"
        assert svc["pids_limit"] == 256


def test_existing_stricter_limits_are_preserved():
    compose = yaml.safe_dump(
        {"services": {"app": {"image": "x", "cpus": 0.25, "mem_limit": "128m"}}}
    )
    out = yaml.safe_load(apply_resource_limits(compose, cpu_millicores=2000, mem_mb=1024))
    # A template's own (stricter) limits win; we only fill gaps.
    assert out["services"]["app"]["cpus"] == 0.25
    assert out["services"]["app"]["mem_limit"] == "128m"


def test_zero_or_missing_allocation_is_a_noop_for_that_field():
    out = yaml.safe_load(apply_resource_limits(_TWO_SERVICE, cpu_millicores=0, mem_mb=0))
    svc = out["services"]["app"]
    assert "cpus" not in svc and "mem_limit" not in svc
    assert svc["pids_limit"] > 0  # pids cap still applied (fork-bomb defense)


def test_bad_yaml_passes_through_unchanged():
    assert apply_resource_limits(":::not yaml", cpu_millicores=500, mem_mb=512) == ":::not yaml"
