"""Smoke tests — verify the test infrastructure itself is working."""


def test_arithmetic_works():
    """If this fails, Python is broken."""
    assert 1 + 1 == 2


def test_imports_work():
    """If this fails, the project's package layout is broken."""
    from watchtower import config
    from watchtower import eumdac_client
    from watchtower import collector
    assert config is not None
    assert eumdac_client is not None
    assert collector is not None