from app.provider import TwelveDataProvider, get_provider


def test_get_provider_returns_none_when_unconfigured():
    assert get_provider("", "https://api.twelvedata.com") is None


def test_get_provider_returns_a_client_when_configured():
    provider = get_provider("fake-key", "https://api.twelvedata.com")
    assert isinstance(provider, TwelveDataProvider)
