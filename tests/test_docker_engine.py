import asyncio

import pytest

from app.services.docker_engine import (
    DockerEngine,
    DockerEngineError,
    _parse_json_objects,
    sanitize_project_name,
)


def _engine(runner):
    return DockerEngine(runner=runner)


def test_deploy_stack_pipes_compose_and_sanitizes_project():
    calls: list[tuple] = []

    async def runner(argv, stdin, env):
        calls.append((argv, stdin, env))
        return (0, "", "")

    result = asyncio.run(
        _engine(runner).deploy_stack("My WP App!", "services: {}", {"SERVICE_PASSWORD_X": "secret"})
    )
    assert result == {"ok": True, "project": "my-wp-app"}
    argv, stdin, env = calls[0]
    assert argv[:2] == ["docker", "compose"]
    assert "-p" in argv and "my-wp-app" in argv
    assert "up" in argv and "-d" in argv
    assert stdin == "services: {}"
    assert env == {"SERVICE_PASSWORD_X": "secret"}


def test_nonzero_exit_raises_with_stderr():
    async def runner(argv, stdin, env):
        return (1, "", "compose explode")

    with pytest.raises(DockerEngineError) as exc:
        asyncio.run(_engine(runner).version())
    assert "compose explode" in str(exc.value)
    assert exc.value.code == 502  # subprocess exit code goes in the message, not as HTTP status


def test_list_stacks_parses_json_array():
    async def runner(argv, stdin, env):
        return (0, '[{"Name":"wp","Status":"running(2)"}]', "")

    stacks = asyncio.run(_engine(runner).list_stacks())
    assert stacks == [{"Name": "wp", "Status": "running(2)"}]


def test_remove_stack_passes_volumes_flag():
    calls: list[list[str]] = []

    async def runner(argv, stdin, env):
        calls.append(argv)
        return (0, "", "")

    asyncio.run(_engine(runner).remove_stack("blog", volumes=True))
    assert "down" in calls[0] and "--volumes" in calls[0]


def test_parse_json_objects_handles_ndjson_and_blank():
    assert _parse_json_objects('{"Name":"a"}\n{"Name":"b"}') == [{"Name": "a"}, {"Name": "b"}]
    assert _parse_json_objects("") == []
    assert _parse_json_objects("not json") == []


def test_sanitize_project_name():
    assert sanitize_project_name("My WP App!") == "my-wp-app"
    assert sanitize_project_name("  ") == "app"
    assert sanitize_project_name("Already-ok_1") == "already-ok_1"


def test_restart_stack_runs_compose_restart():
    calls: list[list[str]] = []

    async def runner(argv, stdin, env):
        calls.append(argv)
        return (0, "", "")

    assert asyncio.run(_engine(runner).restart_stack("My Blog")) == {
        "ok": True, "project": "my-blog"
    }
    assert calls == [["docker", "compose", "-p", "my-blog", "restart"]]


def test_stack_mounts_lists_volumes_without_host_paths():
    inspect = """[
      {"Config": {"Labels": {"com.docker.compose.service": "wordpress"}},
       "Mounts": [
         {"Type": "volume", "Name": "blog_wp-data", "Source": "/var/lib/docker/volumes/x",
          "Destination": "/var/www/html", "RW": true},
         {"Type": "bind", "Source": "/opt/secret/php.ini",
          "Destination": "/usr/local/etc/php/php.ini", "RW": false}
       ]},
      {"Config": {"Labels": {"com.docker.compose.service": "db"}},
       "Mounts": [{"Type": "volume", "Name": "blog_db", "Destination": "/var/lib/mysql",
                   "RW": true}]}
    ]"""

    async def runner(argv, stdin, env):
        if argv[1:3] == ["compose", "-p"]:
            return (0, '[{"ID": "c1"}, {"ID": "c2"}]', "")
        assert argv[1:] == ["inspect", "c1", "c2"]
        return (0, inspect, "")

    mounts = asyncio.run(_engine(runner).stack_mounts("blog"))
    assert mounts == [
        {"service": "db", "type": "volume", "name": "blog_db",
         "destination": "/var/lib/mysql", "read_only": False},
        {"service": "wordpress", "type": "bind", "name": "",
         "destination": "/usr/local/etc/php/php.ini", "read_only": True},
        {"service": "wordpress", "type": "volume", "name": "blog_wp-data",
         "destination": "/var/www/html", "read_only": False},
    ]
    assert "/opt/secret" not in str(mounts)


def test_stack_mounts_without_containers_skips_inspect():
    async def runner(argv, stdin, env):
        assert "inspect" not in argv
        return (0, "", "")

    assert asyncio.run(_engine(runner).stack_mounts("gone")) == []
