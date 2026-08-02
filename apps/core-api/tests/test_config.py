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
