import fakeredis.aioredis
import pytest

from app.categorizer import CATEGORY_TAXONOMY, categorize_by_rules, categorize_with_ai_fallback
from app.config import Settings


@pytest.mark.parametrize(
    "merchant_name,expected_category",
    [
        ("Starbucks #1234", "Food & Dining"),
        ("UBER   TRIP", "Transportation"),
        ("NETFLIX.COM", "Entertainment"),
        ("AMAZON MKTPLACE", "Shopping"),
        ("CVS PHARMACY", "Health"),
        ("PAYROLL DIRECT DEPOSIT", "Income"),
        ("VENMO PAYMENT", "Transfer"),
    ],
)
def test_categorize_by_rules_matches_known_merchants(merchant_name, expected_category):
    assert categorize_by_rules(merchant_name) == expected_category


def test_categorize_by_rules_returns_none_for_unrecognized_merchant():
    assert categorize_by_rules("Some Obscure Local Shop") is None


def test_categorize_by_rules_is_case_insensitive():
    assert categorize_by_rules("STARBUCKS") == categorize_by_rules("starbucks")


async def test_ai_fallback_returns_none_when_openai_not_configured():
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    settings = Settings(openai_api_key="")

    result = await categorize_with_ai_fallback("Some Obscure Shop", redis_client, settings)

    assert result is None
    await redis_client.aclose()


async def test_ai_fallback_uses_cached_value_without_calling_openai(monkeypatch):
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    settings = Settings(openai_api_key="fake-key-not-actually-used")
    await redis_client.set("ai_category:some obscure shop", '"Shopping"')

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("OpenAI should not be called when the cache already has a value")

    monkeypatch.setattr("app.categorizer.AsyncOpenAI", _fail_if_called)

    result = await categorize_with_ai_fallback("Some Obscure Shop", redis_client, settings)

    assert result == "Shopping"
    await redis_client.aclose()


async def test_ai_fallback_rejects_a_category_outside_the_taxonomy(monkeypatch):
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    settings = Settings(openai_api_key="fake-key")

    class _FakeChoice:
        class _Message:
            content = "Not A Real Category"

        message = _Message()

    class _FakeResponse:
        def __init__(self):
            self.choices = [_FakeChoice()]

    class _FakeCompletions:
        async def create(self, **kwargs):
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeAsyncOpenAI:
        def __init__(self, api_key):
            self.chat = _FakeChat()

    monkeypatch.setattr("app.categorizer.AsyncOpenAI", _FakeAsyncOpenAI)

    result = await categorize_with_ai_fallback("Weird Merchant", redis_client, settings)

    assert result is None  # never guesses outside the known taxonomy
    await redis_client.aclose()


async def test_ai_fallback_returns_none_and_does_not_raise_when_openai_call_fails(monkeypatch):
    redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    settings = Settings(openai_api_key="fake-key")

    class _FakeCompletions:
        async def create(self, **kwargs):
            raise ConnectionError("simulated network failure")

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeAsyncOpenAI:
        def __init__(self, api_key):
            self.chat = _FakeChat()

    monkeypatch.setattr("app.categorizer.AsyncOpenAI", _FakeAsyncOpenAI)

    result = await categorize_with_ai_fallback("Weird Merchant", redis_client, settings)

    assert result is None
    await redis_client.aclose()


def test_taxonomy_matches_the_seeded_categories_taxonomy():
    # Mirrors apps/core-api's Phase 3 seed migration taxonomy exactly —
    # a category this service can return that doesn't exist in that
    # table would silently fail the category_id lookup downstream.
    assert CATEGORY_TAXONOMY == [
        "Income",
        "Housing",
        "Transportation",
        "Food & Dining",
        "Shopping",
        "Entertainment",
        "Health",
        "Bills & Utilities",
        "Savings & Investments",
        "Transfer",
        "Other",
    ]
