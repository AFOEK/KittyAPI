import pytest

from crash_engine import (
    generate_season_schedule,
    seasonal_crash_time,
)

@pytest.fixture
def mock_round_plan(monkeypatch):

    def configure(crash_point=2.0):
        schedule = generate_season_schedule(
            bytes(32)
        )

        plan = {
            "crash_point": crash_point,
            "crash_time": seasonal_crash_time(
                crash_point,
                schedule,
                warmup=3.0,
            ),
            "schedule": schedule,
            "distraction": "fish",
            "warmup": 3.0,
        }

        monkeypatch.setattr(
            "round_manager.generate_round_plan",
            lambda mode: plan,
        )

        return plan

    return configure