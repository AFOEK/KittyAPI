import pytest
import math

from crash_engine import (
    MIN_CRASH_SECONDS,
    multiplier_at,
    crash_after_seconds,
    select_distraction,
    season_growth_rate,
    seasonal_multiplier_at,
    current_season,
)


def test_minimum_crash_time():
    for rate in [0.085, 0.12, 0.13, 0.20]:
        for crash_point in [1.0, 1.5, 2.0, 5.0]:
            t = crash_after_seconds(
                crash_point,
                growth_rate=rate,
                lead_in_seconds=MIN_CRASH_SECONDS
            )

            assert t >= 3.0


def test_warmup_multiplier():
    for elapsed in [0.0, 1.0, 2.0, 2.9]:
        assert multiplier_at(
            elapsed,
            growth_rate=0.12,
            lead_in_seconds=3.0
        ) == 1.0


def test_season_transition():
    schedule = [
        {
            "season": "spring",
            "start": 0.0,
            "end": 2.0,
            "growth_rate": 0.12,
            "rush": False,
        },
        {
            "season": "summer",
            "start": 2.0,
            "end": 5.0,
            "growth_rate": 0.20,
            "rush": True,
        },
        {
            "season": "fall",
            "start": 5.0,
            "end": 10.0,
            "growth_rate": 0.12,
            "rush": False,
        },
    ]

    # Three seconds warm-up, then three active seconds.
    elapsed = 6.0

    segment = current_season(
        elapsed, schedule, warmup=3.0
    )

    multiplier = seasonal_multiplier_at(
        elapsed, schedule, warmup=3.0
    )

    assert segment["season"] == "summer"
    assert segment["rush"] is True
    assert math.floor(multiplier * 100) / 100 == 1.55

def test_winter_slower_than_spring():
    spring_rate, _ = season_growth_rate("spring")
    winter_rate, _ = season_growth_rate("winter")

    assert winter_rate < spring_rate


def test_summer_rush(monkeypatch):
    monkeypatch.setattr(
        "crash_engine.generate_random",
        lambda **kwargs: {"normalized": 0.10}
    )

    growth, rush = season_growth_rate("summer")

    assert rush is True
    assert growth == 0.20


def test_summer_no_rush(monkeypatch):
    monkeypatch.setattr(
        "crash_engine.generate_random",
        lambda **kwargs: {"normalized": 0.80}
    )

    growth, rush = season_growth_rate("summer")

    assert rush is False
    assert growth == 0.13


def test_distractions():
    for season in ["spring", "summer", "fall", "winter"]:
        event = select_distraction(season)
        assert isinstance(event, str)