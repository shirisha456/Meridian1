import pytest

from app.core.config import Settings


def test_cors_origin_list_splits_and_strips():
    settings = Settings(cors_origins="http://localhost:3000, https://app.example.com ")
    assert settings.cors_origin_list == ["http://localhost:3000", "https://app.example.com"]


def test_cors_origin_list_empty_string_yields_empty_list():
    settings = Settings(cors_origins="")
    assert settings.cors_origin_list == []


def test_is_production_flag():
    assert Settings(environment="production").is_production is True
    assert Settings(environment="development").is_production is False


def test_is_test_flag():
    assert Settings(environment="test").is_test is True
    assert Settings(environment="development").is_test is False


def test_refuses_to_start_in_production_with_placeholder_jwt_secret():
    settings = Settings(environment="production")  # jwt_secret left at its default
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.assert_safe_for_environment()


def test_allows_production_start_with_a_real_jwt_secret():
    settings = Settings(environment="production", jwt_secret="a-real-random-secret-value")
    settings.assert_safe_for_environment()  # must not raise


def test_allows_development_start_with_placeholder_jwt_secret():
    settings = Settings(environment="development")
    settings.assert_safe_for_environment()  # must not raise outside production
