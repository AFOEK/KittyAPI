from crash_engine import crash_from_uniform, crash_after_seconds, multiplier_at
from crash_engine import generate_crash_point, crash_after_seconds, select_distraction
from economy import calculate_cashout
from decimal import Decimal

def test_crash_distribution():
    assert crash_from_uniform(0.48) == 2.0
    assert crash_from_uniform(0.24) == 4.0
    assert crash_from_uniform(0.99) == 1.0

def test_multiplier():
    assert multiplier_at(0) == 1.0
    assert abs(multiplier_at(5) - 2.4596) < 0.001

def test_successful_cashout():
    payout = calculate_cashout(
        wager=Decimal("100"),
        elapsed_seconds=5.0,
        crash_point=3.0
    )

    assert payout == Decimal("245.96")

def test_failed_cashout():
    payout = calculate_cashout(
        wager=Decimal("100"),
        elapsed_seconds=10.0,
        crash_point=3.0
    )

    assert payout is None

crash_point = generate_crash_point("hybrid")

print("Crash multiplier:", crash_point)
print("Crash after:", crash_after_seconds(crash_point))
print("Distraction:", select_distraction())