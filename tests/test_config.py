"""Unit tests for the config module."""
import pytest


@pytest.fixture
def fake_env(monkeypatch):
    """Set the bare-minimum env vars Settings requires."""
    monkeypatch.setenv("EUMETSAT_CONSUMER_KEY", "fake-key")
    monkeypatch.setenv("EUMETSAT_CONSUMER_SECRET", "fake-secret")
    return monkeypatch


def test_collections_parses_single_item(fake_env):
    """A single collection ID should produce a one-element list."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "EO:EUM:DAT:MSG")
    from watchtower.config import Settings
    settings = Settings()
    assert settings.collections == ["EO:EUM:DAT:MSG"]


def test_collections_parses_comma_separated(fake_env):
    """Comma-separated values should produce a list of multiple items."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "EO:EUM:DAT:MSG,EO:EUM:DAT:METOP")
    from watchtower.config import Settings
    settings = Settings()
    assert settings.collections == ["EO:EUM:DAT:MSG", "EO:EUM:DAT:METOP"]


def test_collections_strips_whitespace_around_items(fake_env):
    """Spaces after commas should be removed silently."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "A, B, C")
    from watchtower.config import Settings
    settings = Settings()
    assert settings.collections == ["A", "B", "C"]


def test_collections_filters_out_empty_items(fake_env):
    """Empty items from typos should be silently dropped."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "A,,B,")
    from watchtower.config import Settings
    settings = Settings()
    assert settings.collections == ["A", "B"]


def test_collections_handles_empty_string(fake_env):
    """An empty WATCHTOWER_COLLECTIONS should produce an empty list."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "")
    from watchtower.config import Settings
    settings = Settings()
    assert settings.collections == []