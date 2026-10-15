from decimal import Decimal
from round_manager import RoundManager
from unittest.mock import patch

def test_create_session():
    manager = RoundManager()

    session = manager.create_session()

    assert session["balance"] == "1000.00"
    assert session["session_id"] in manager.sessions

def test_start_round(monkeypatch):
    monkeypatch.setattr("round_manager.generate_crash_point", lambda mode: 2.0)
    monkeypatch.setattr("round_manager.select_distraction", lambda: "fish")
    manager = RoundManager()
    session = manager.create_session()
    session_id = session["session_id"]
    result = manager.start_round(session_id, Decimal("100.00"))
    assert result["status"] == "running"
    assert result["balance"] == "900.00"
    assert "crash_point" not in result

def test_successful_cashout(monkeypatch):
    monkeypatch.setattr("round_manager.generate_crash_point", lambda mode: 2.0)
    clock = [100.0]
    manager = RoundManager( clock=lambda: clock[0])
    session = manager.create_session()
    session_id = session["session_id"]
    round_data = manager.start_round(session_id, Decimal("100.00"))
    round_id = round_data["round_id"]
    # Advance the clock by one second.
    clock[0] += 1.0
    result = manager.cash_out(session_id, round_id)
    assert result["status"] == "cashed_out"
    assert result["payout"] == "119.00"
    assert result["balance"] == "1019.00"

def test_duplicate_cashout(monkeypatch):
    monkeypatch.setattr("round_manager.generate_crash_point", lambda mode: 2.0)
    clock = [100.0]
    manager = RoundManager(clock=lambda: clock[0])
    session_id = manager.create_session()["session_id"]
    round_id = manager.start_round(session_id, Decimal("100.00"))["round_id"]
    clock[0] += 1.0
    first = manager.cash_out(session_id, round_id)
    second = manager.cash_out(session_id, round_id)
    assert first["payout"] == second["payout"]
    assert manager.get_balance(session_id)["balance"] == "1019.00"

def test_crashed_round(monkeypatch):
    monkeypatch.setattr("round_manager.generate_crash_point", lambda mode: 2.0)
    clock = [100.0]
    manager = RoundManager(clock=lambda: clock[0])
    session_id = manager.create_session()["session_id"]
    round_id = manager.start_round(session_id, Decimal("100.00"))["round_id"]
    # Advance beyond the 2x crash deadline.
    clock[0] += 5.0
    result = manager.cash_out(session_id, round_id)
    assert result["status"] == "crashed"
    assert result["payout"] == "0.00"
    assert result["balance"] == "900.00"

def test_round_lifecycle():
    clock = [100.0]
    manager = RoundManager(clock=lambda: clock[0])

    session = manager.create_session()
    session_id = session["session_id"]

    with (patch("round_manager.generate_crash_point", return_value=3.0), patch("round_manager.select_distraction", return_value="fish")):
        round_data = manager.start_round(session_id, Decimal("100.00"))

    round_id = round_data["round_id"]

    assert round_data["balance"] == "900.00"
    assert round_data["status"] == "running"

    clock[0] += 3.0
    state = manager.get_round_state(session_id, round_id)

    assert state["status"] == "running"
    assert state["multiplier"] == 1.71

    result = manager.cash_out(session_id, round_id)

    assert result["status"] == "cashed_out"
    assert result["payout"] == "171.00"
    assert result["balance"] == "1071.00"

    # Try cashing out again.
    duplicate = manager.cash_out(session_id, round_id)
    assert duplicate["payout"] == "171.00"
    assert manager.get_balance(session_id)["balance"] == "1071.00"