import pytest


@pytest.fixture(autouse=True)
def fixed_test_season(monkeypatch):
    monkeypatch.setattr(
        "round_manager.select_season",
        lambda: "spring"
    )