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


def test_detect_port_reads_first_expose():
    async def runner(argv, cwd):
        if "inspect" in argv:
            return (0, '{"3000/tcp":{}}', "")
        return (0, "", "")

    assert asyncio.run(Builder(runner=runner).detect_port("img:1")) == 3000


def test_build_streams_output_lines_to_sink():
    """When on_line is given, the build step forwards each output line live."""
    rec: list[list[str]] = []

    async def stream_runner(argv, cwd, sink):
        for line in ["Step 1/3 : FROM python", "Step 2/3 : COPY .", "Successfully built abc"]:
            await sink(line)
        return 0, "\n".join(["Step 1/3 : FROM python", "Step 2/3 : COPY .", "Successfully built abc"])

    seen: list[str] = []

    async def on_line(line):
        seen.append(line)

    builder = Builder(runner=make_runner(rec, has_dockerfile=True), stream_runner=stream_runner)
    asyncio.run(builder.build("/src", "img:1", on_line=on_line))
    assert seen == ["Step 1/3 : FROM python", "Step 2/3 : COPY .", "Successfully built abc"]


def test_build_raises_on_nonzero_exit():
    async def runner(argv, cwd):
        if argv[:2] == ["test", "-f"]:
            return (1, "", "")  # no Dockerfile -> nixpacks path
        return (1, "", "kaboom")

    with pytest.raises(BuildError) as exc:
        asyncio.run(Builder(runner=runner).build("/src", "img:1"))
    assert "kaboom" in str(exc.value)
    assert exc.value.code == 502


def test_clone_injects_github_token_for_private_repo():
    rec: list[list[str]] = []
    builder = Builder(runner=make_runner(rec, has_dockerfile=True), github_token="ghp_secret")
    asyncio.run(builder.build_from_git("https://github.com/x/y", "main", project="p"))
    clone = next(a for a in rec if a[:2] == ["git", "clone"])
    assert any("https://x-access-token:ghp_secret@github.com/x/y" == part for part in clone)


def test_clone_hints_private_repo_when_no_token():
    async def runner(argv, cwd):
        if argv[:2] == ["git", "clone"]:
            return (128, "", "fatal: could not read Username for 'https://github.com': No such device or address")
        return (0, "", "")

    with pytest.raises(BuildError) as exc:
        asyncio.run(Builder(runner=runner).build_from_git("https://github.com/x/y", "main", project="p"))
    msg = str(exc.value)
    assert "private repository" in msg.lower()
    assert "GITHUB_TOKEN" in msg


def test_clone_scrubs_token_from_errors():
    async def runner(argv, cwd):
        if argv[:2] == ["git", "clone"]:
            return (128, "", "fatal: Authentication failed for 'https://x-access-token:ghp_secret@github.com/x/y'")
        return (0, "", "")

    builder = Builder(runner=runner, github_token="ghp_secret")
    with pytest.raises(BuildError) as exc:
        asyncio.run(builder.build_from_git("https://github.com/x/y", "main", project="p"))
    msg = str(exc.value)
    assert "ghp_secret" not in msg
    assert "x-access-token" not in msg
