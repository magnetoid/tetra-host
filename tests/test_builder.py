import asyncio

import pytest

from app.services.builder import Builder, BuildError


def make_runner(record, *, has_dockerfile=True, sha="abcdef1234567890"):
    async def runner(argv, cwd):
        record.append(argv)
        if argv[:2] == ["test", "-f"]:
            return (0 if has_dockerfile else 1, "", "")
        if "rev-parse" in argv:
            return (0, sha + "\n", "")
        return (0, "", "")

    return runner


def test_build_uses_dockerfile_when_present():
    rec: list[list[str]] = []
    result = asyncio.run(Builder(runner=make_runner(rec, has_dockerfile=True)).build("/src", "img:1"))
    assert result.builder == "dockerfile"
    assert ["docker", "build", "-t", "img:1", "/src"] in rec


def test_build_falls_back_to_nixpacks():
    rec: list[list[str]] = []
    result = asyncio.run(Builder(runner=make_runner(rec, has_dockerfile=False)).build("/src", "img:1"))
    assert result.builder == "nixpacks"
    assert any(a[:2] == ["nixpacks", "build"] for a in rec)


def test_build_from_git_tags_with_commit_sha():
    rec: list[list[str]] = []
    builder = Builder(runner=make_runner(rec, has_dockerfile=True, sha="abcdef1234567890"))
    result = asyncio.run(builder.build_from_git("https://github.com/x/y", "main", project="myapp"))
    assert result.image == "tetra-myapp:abcdef123456"  # sha[:12]
    assert result.commit == "abcdef1234567890"
    assert any(a[:4] == ["git", "clone", "--depth", "1"] for a in rec)
    assert any(a[:2] == ["docker", "build"] for a in rec)


def test_build_raises_on_nonzero_exit():
    async def runner(argv, cwd):
        if argv[:2] == ["test", "-f"]:
            return (1, "", "")  # no Dockerfile -> nixpacks path
        return (1, "", "kaboom")

    with pytest.raises(BuildError) as exc:
        asyncio.run(Builder(runner=runner).build("/src", "img:1"))
    assert "kaboom" in str(exc.value)
    assert exc.value.code == 502
