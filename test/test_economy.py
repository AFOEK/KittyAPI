from decimal import Decimal
from economy import place_bet, calculate_cashout, credit_winnings, calculate_profit
import pytest

def test_place_bet():
    balance = place_bet(Decimal("1000.00"), Decimal("100.00"))
    assert balance == Decimal("900.00")

def test_cashout():
    payout = calculate_cashout(Decimal("100.00"), 2.5)
    assert payout == Decimal("250.00")

def test_winning_round():
    balance = Decimal("1000.00")
    wager = Decimal("100.00")
    balance = place_bet(balance, wager)
    payout = calculate_cashout(wager, 2.5)
    balance = credit_winnings(balance, payout)
    assert balance == Decimal("1150.00")

def test_crashed_round():
    balance = Decimal("1000.00")
    wager = Decimal("100.00")
    balance = place_bet(balance, wager)
    assert balance == Decimal("900.00")
    profit = calculate_profit(wager, Decimal("0.00"))
    assert profit == Decimal("-100.00")

def test_insufficient_balance():
    with pytest.raises(ValueError):
        place_bet(Decimal("100.00"), Decimal("200.00"))