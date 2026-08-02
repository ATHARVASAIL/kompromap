"""Guards on the Docker/deployment wiring.

These exist because of a real bug: the dev docker-compose.yml originally
started uvicorn directly and never ran `alembic upgrade head`, so a fresh
Postgres volume came up with zero tables and *every* API call returned a
500 ("relation does not exist") — while /api/health, which doesn't touch
the DB, misleadingly still returned 200. Nothing in the test suite caught
it, because the suite runs against SQLite with tables created directly
from the models rather than through the containers.

These are static checks on the Dockerfiles/scripts rather than a real
container build (too slow and Docker-dependent for a unit test run), but
they pin the specific things that broke.
"""
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

DEV_ENTRYPOINT = BACKEND_DIR / "docker-entrypoint.dev.sh"
PROD_ENTRYPOINT = BACKEND_DIR / "docker-entrypoint.prod.sh"
DEV_DOCKERFILE = BACKEND_DIR / "Dockerfile"
PROD_DOCKERFILE = BACKEND_DIR / "Dockerfile.prod"


@pytest.mark.parametrize("script", [DEV_ENTRYPOINT, PROD_ENTRYPOINT])
def test_entrypoint_exists(script):
    assert script.is_file(), f"{script.name} is missing"


@pytest.mark.parametrize("script", [DEV_ENTRYPOINT, PROD_ENTRYPOINT])
def test_entrypoint_runs_migrations(script):
    """The actual bug: without this, every endpoint 500s on a fresh DB."""
    assert "alembic upgrade head" in script.read_text()


@pytest.mark.parametrize("script", [DEV_ENTRYPOINT, PROD_ENTRYPOINT])
def test_entrypoint_starts_uvicorn_after_migrating(script):
    content = script.read_text()
    migrate_at = content.index("alembic upgrade head")
    serve_at = content.index("uvicorn")
    assert migrate_at < serve_at, "migrations must run before the server starts"


@pytest.mark.parametrize("script", [DEV_ENTRYPOINT, PROD_ENTRYPOINT])
def test_entrypoint_has_unix_line_endings(script):
    """CRLF in a shell script fails inside a Linux container with a
    confusing 'not found' error. .gitattributes pins this too, but check
    the committed bytes directly."""
    assert b"\r\n" not in script.read_bytes(), f"{script.name} has CRLF line endings"


@pytest.mark.parametrize(
    "dockerfile,script_name",
    [(DEV_DOCKERFILE, "docker-entrypoint.dev.sh"), (PROD_DOCKERFILE, "docker-entrypoint.prod.sh")],
)
def test_dockerfile_uses_the_entrypoint_script(dockerfile, script_name):
    content = dockerfile.read_text()
    assert "ENTRYPOINT" in content
    assert script_name in content


@pytest.mark.parametrize("dockerfile", [DEV_DOCKERFILE, PROD_DOCKERFILE])
def test_dockerfile_invokes_entrypoint_via_sh(dockerfile):
    """docker-compose.yml bind-mounts ./backend over /app, masking any
    build-time chmod +x — and Windows hosts have no execute bit at all —
    so the script must be invoked through `sh` explicitly."""
    content = dockerfile.read_text()
    assert 'ENTRYPOINT ["sh"' in content, "entrypoint must be invoked via sh, not relying on the execute bit"


@pytest.mark.parametrize("dockerfile", [DEV_DOCKERFILE, PROD_DOCKERFILE])
def test_dockerfile_pins_debian_release(dockerfile):
    """Floating `python:3.11-slim` currently resolves to Debian trixie,
    whose mirrors have had apt hash-sum mismatches that hard-fail builds."""
    content = dockerfile.read_text()
    assert "python:3.11-slim-bookworm" in content


def test_gitattributes_forces_lf_on_shell_scripts():
    gitattributes = REPO_ROOT / ".gitattributes"
    assert gitattributes.is_file(), ".gitattributes is missing"
    assert "*.sh text eol=lf" in gitattributes.read_text()


# --- Vite dev-proxy wiring -------------------------------------------------
# Second real bug: the frontend's Vite dev server proxies /api/* to the
# backend, but inside docker-compose "localhost" resolves to the *frontend
# container itself*, not the backend. Every API call failed with
# "ECONNREFUSED 127.0.0.1:8000" and surfaced in the browser as a 500 —
# while the backend logs looked completely healthy, which made it
# genuinely confusing to diagnose.

VITE_CONFIG = REPO_ROOT / "frontend" / "vite.config.ts"
DEV_COMPOSE = REPO_ROOT / "docker-compose.yml"


def test_vite_config_reads_proxy_target_from_env():
    assert VITE_CONFIG.is_file(), "frontend/vite.config.ts is missing"
    content = VITE_CONFIG.read_text()
    assert "VITE_PROXY_TARGET" in content, (
        "vite.config.ts must read VITE_PROXY_TARGET so the compose setup can point "
        "the dev proxy at the backend service instead of the frontend container itself"
    )


def test_vite_config_falls_back_to_localhost_outside_docker():
    """Plain `npm run dev` on a developer machine has no env var set, and
    localhost is correct there — the fallback must not be removed."""
    content = VITE_CONFIG.read_text()
    assert "localhost:8000" in content


def test_dev_compose_sets_proxy_target_to_backend_service():
    content = DEV_COMPOSE.read_text()
    assert "VITE_PROXY_TARGET" in content, (
        "docker-compose.yml must set VITE_PROXY_TARGET for the frontend service"
    )
    assert "http://backend:8000" in content, (
        "the proxy must target the compose service name 'backend', not localhost"
    )


def test_vite_proxy_target_is_configurable():
    """The Vite dev-server proxy must not hardcode localhost:8000.

    Inside docker-compose, "localhost" resolves to the frontend container
    itself, not the backend — a hardcoded localhost target makes every
    /api/* call fail with ECONNREFUSED, surfacing in the browser as a
    generic 500 on every page while the backend is actually healthy.
    """
    vite_config = (REPO_ROOT / "frontend" / "vite.config.ts").read_text()
    assert "VITE_PROXY_TARGET" in vite_config, (
        "vite.config.ts must read the proxy target from VITE_PROXY_TARGET "
        "so docker-compose can point it at the backend service"
    )


def test_compose_sets_vite_proxy_target_to_backend_service():
    compose = (REPO_ROOT / "docker-compose.yml").read_text()
    assert "VITE_PROXY_TARGET" in compose, "docker-compose.yml must set VITE_PROXY_TARGET"
    assert "http://backend:8000" in compose, (
        "the proxy must target the compose service name, not localhost"
    )


# --- Import file-picker filters --------------------------------------------
# Third real bug: the file input in ImportPage had no `key`, so React reused
# the same DOM node when switching tools and never re-applied the new
# `accept` attribute — the picker stayed stuck on Nmap's ".xml" and refused
# to show .json/.jsonl/.txt files at all.

IMPORT_PAGE = REPO_ROOT / "frontend" / "src" / "pages" / "ImportPage.tsx"


def test_import_file_input_is_keyed_on_tool():
    """Without key={tool}, React reuses the input element and the accept
    filter goes stale when the user switches tools."""
    content = IMPORT_PAGE.read_text()
    assert "key={tool}" in content, (
        "the file input must be keyed on the selected tool so React remounts it "
        "and re-applies the accept filter"
    )


def test_import_accept_filters_include_wildcard_fallback():
    """accept= is a picker hint, not validation — the backend parses by
    content. Real tool output often has odd extensions (.out, .log, none),
    so every filter ends with * to avoid hard-blocking valid files."""
    content = IMPORT_PAGE.read_text()
    for fragment in [".xml,*", ".json,.jsonl,.txt,*", ".txt,.json,.jsonl,*"]:
        assert fragment in content, f"missing wildcard fallback in accept filter: {fragment}"
