from crash_engine import crash_from_uniform, crash_after_seconds, multiplier_at
from crash_engine import generate_crash_point, crash_after_seconds, select_distraction

def test_crash_distribution():
    assert crash_from_uniform(0.48) == 2.0
    assert crash_from_uniform(0.24) == 4.0
    assert crash_from_uniform(0.99) == 1.0

def test_multiplier():
    assert multiplier_at(0) == 1.0
    assert abs(multiplier_at(5) - 2.4596) < 0.001