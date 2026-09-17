"""Settings loaded from a real .env file.

These exist because a bug escaped the whole suite: CORS_ORIGINS is a list, and
pydantic-settings JSON-decodes list fields from dotenv before validators run, so
the plain comma-separated form documented in .env.example crashed the app at
startup with a JSONDecodeError. Every other test configured settings in code, so
the dotenv path was never exercised.
"""
import textwrap

import pytest
from pydantic_settings import BaseSettings

from app.config import Settings


def _settings_from(tmp_path, body: str) -> Settings:
    """Load Settings from a throwaway .env, ignoring the real environment."""
    env_file = tmp_path / ".env"
    env_file.write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")

    class Isolated(Settings):
        model_config = {
            **BaseSettings.model_config,
            "env_file": str(env_file),
            "env_file_encoding": "utf-8",
            "extra": "ignore",
        }

    return Isolated()


class TestCorsOriginsFromDotenv:
    def test_comma_separated_form_documented_in_env_example(self, tmp_path):
        settings = _settings_from(
            tmp_path,
            """
            JWT_SECRET=rahasia
            CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
            """,
        )
        assert settings.cors_origins == [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    def test_single_origin(self, tmp_path):
        settings = _settings_from(tmp_path, "CORS_ORIGINS=https://app.example.com")
        assert settings.cors_origins == ["https://app.example.com"]

    def test_surrounding_whitespace_is_trimmed(self, tmp_path):
        settings = _settings_from(
            tmp_path, "CORS_ORIGINS=https://a.example.com , https://b.example.com"
        )
        assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]

    def test_empty_value_falls_back_to_no_origins(self, tmp_path):
        settings = _settings_from(tmp_path, "CORS_ORIGINS=")
        assert settings.cors_origins == []

    def test_absent_value_uses_the_default(self, tmp_path):
        settings = _settings_from(tmp_path, "JWT_SECRET=rahasia")
        assert settings.cors_origins == [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]


class TestOtherFieldsFromDotenv:
    def test_scalars_and_booleans_parse(self, tmp_path):
        settings = _settings_from(
            tmp_path,
            """
            MONGO_URI=mongodb://127.0.0.1:27017
            MONGO_DB=umkm_test
            SCRAPER_RESPECT_ROBOTS=false
            SCRAPER_DELAY_SECONDS=2.5
            SCRAPER_MAX_PAGES_PER_SITE=9
            DUITKU_PRODUCTION=true
            """,
        )
        assert settings.mongo_uri == "mongodb://127.0.0.1:27017"
        assert settings.mongo_db == "umkm_test"
        assert settings.scraper_respect_robots is False
        assert settings.scraper_delay_seconds == 2.5
        assert settings.scraper_max_pages_per_site == 9
        assert settings.duitku_production is True

    def test_values_containing_commas_are_not_split(self, tmp_path):
        """Only cors_origins is a list; a scalar must keep its commas."""
        settings = _settings_from(
            tmp_path, "SCRAPER_USER_AGENT=Bot/1.0 (a, b, c)"
        )
        assert settings.scraper_user_agent == "Bot/1.0 (a, b, c)"

    def test_env_example_parses_as_written(self, tmp_path):
        """The shipped example must actually load - it is what users copy."""
        from pathlib import Path

        example = Path(__file__).resolve().parents[1] / ".env.example"
        if not example.is_file():
            pytest.skip(".env.example tidak ditemukan")

        lines = [
            line
            for line in example.read_text(encoding="utf-8").splitlines()
            # Drop the generate-me placeholder that is not a real value.
            if line.strip() and not line.strip().startswith("#")
        ]
        settings = _settings_from(tmp_path, "\n".join(lines))
        assert isinstance(settings.cors_origins, list)
        assert settings.mongo_db
