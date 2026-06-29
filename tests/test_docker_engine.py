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
