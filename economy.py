from decimal import Decimal, ROUND_HALF_UP

INITIAL_BALANCE = Decimal("1000.00")
MIN_BET = Decimal("1.00")
MAX_BET = Decimal("500.00")
CREDIT_PRECISION = Decimal("0.01")

def calculate_cashout(wager: Decimal, multiplier: float | Decimal) -> Decimal:
    wager = validate_money(wager)
    if wager <= 0:
        raise ValueError("Wager must be positive")

    m = Decimal(str(multiplier))

    if not m.is_finite() or m < 1:
        raise ValueError("Invalid multiplier")

    payout = wager * m
    return payout.quantize(CREDIT_PRECISION, rounding=ROUND_HALF_UP)

def validate_money(amount: Decimal) -> Decimal:
    if not isinstance(amount, Decimal):
        raise TypeError("Amount must be Decimal")

    if not amount.is_finite():
        raise ValueError("Amount must be finite")

    if amount < 0:
        raise ValueError("Amount cannot be negative")

    rounded = amount.quantize(CREDIT_PRECISION, rounding=ROUND_HALF_UP)
    if amount != rounded:
        raise ValueError("Amount must use at most 2 decimal places")

    return rounded

def place_bet(balance: Decimal, wager: Decimal) -> Decimal:
    balance = validate_money(balance)
    wager = validate_money(wager)
    if not MIN_BET <= wager <= MAX_BET:
        raise ValueError("Wager outside betting limits")

    if wager > balance:
        raise ValueError("Insufficient credits")

    return balance - wager

def credit_winnings(balance: Decimal, payout: Decimal) -> Decimal:
    balance = validate_money(balance)
    payout = validate_money(payout)
    return balance + payout

def calculate_profit(wager: Decimal, payout: Decimal) -> Decimal:
    wager = validate_money(wager)
    payout = validate_money(payout)
    if wager <= 0:
        raise ValueError("Wager must be positive")
    return payout - wager