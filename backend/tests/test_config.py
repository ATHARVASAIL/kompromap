import os

import pytest

from app.core.config import Settings


@pytest.fixture(autouse=True)
def _clean_cors_env():
    original = os.environ.pop("CORS_ORIGINS", None)
    yield
    if original is not None:
        os.environ["CORS_ORIGINS"] = original
    else:
        os.environ.pop("CORS_ORIGINS", None)


def test_cors_origins_default():
    settings = Settings()
    assert settings.cors_origin_list == ["http://localhost:5173", "http://localhost:3000"]


def test_cors_origins_comma_separated_env_var():
    """The natural way to set this in a .env file or docker-compose
    `environment:` block — must not raise, unlike pydantic-settings'
    default JSON-decode behavior for list-typed fields."""
    os.environ["CORS_ORIGINS"] = "https://a.example.com,https://b.example.com"
    settings = Settings()
    assert settings.cors_origin_list == ["https://a.example.com", "https://b.example.com"]


def test_cors_origins_json_array_env_var_still_works():
    os.environ["CORS_ORIGINS"] = '["https://c.example.com", "https://d.example.com"]'
    settings = Settings()
    assert settings.cors_origin_list == ["https://c.example.com", "https://d.example.com"]


def test_cors_origins_single_value():
    os.environ["CORS_ORIGINS"] = "https://only.example.com"
    settings = Settings()
    assert settings.cors_origin_list == ["https://only.example.com"]


def test_cors_origins_strips_whitespace_around_commas():
    os.environ["CORS_ORIGINS"] = "https://a.example.com, https://b.example.com , https://c.example.com"
    settings = Settings()
    assert settings.cors_origin_list == [
        "https://a.example.com",
        "https://b.example.com",
        "https://c.example.com",
    ]
