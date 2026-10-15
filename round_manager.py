import threading
import math
from time import monotonic
from uuid import uuid4
from decimal import Decimal
from crash_engine import crash_after_seconds, multiplier_at, select_distraction, generate_crash_point
from economy import INITIAL_BALANCE, validate_money, place_bet, calculate_cashout, credit_winnings

class RoundManager:
    def __init__(self, clock=monotonic):
        self.sessions = {}
        self.rounds = {}
        self._lock = threading.RLock()
        self._clock = clock

    def create_session(self) -> dict:
        session_id = uuid4().hex
        with self._lock:
            self.sessions[session_id] = {
                "balance": INITIAL_BALANCE,
                "active_round_id": None,
            }

        return {
            "session_id": session_id,
            "balance": str(INITIAL_BALANCE),
        }

    def _owned_round(self, session_id: str, round_id: str) -> dict:
        if session_id not in self.sessions:
            raise KeyError("Session not found")

        round_data = self.rounds.get(round_id)
        if (round_data is None or round_data["session_id"] != session_id):
            raise KeyError("Round not found for session")
        return round_data

    def _refresh_round(self, round_data: dict, now: float) -> None:
        if round_data["status"] != "running":
            return

        elapsed = now - round_data["start_time"]
        if elapsed >= round_data["crash_time"]:
            round_data["status"] = "crashed"
            session = self.sessions[round_data["session_id"]]
            if (session["active_round_id"] == round_data["round_id"]):
                session["active_round_id"] = None

    def _validate_can_start(self, session_id: str, wager: Decimal) -> Decimal:

        session = self.sessions.get(session_id)

        if session is None:
            raise KeyError("Session not found")

        active_id = session["active_round_id"]

        if active_id is not None:
            self._refresh_round(self.rounds[active_id], self._clock())

        if session["active_round_id"] is not None:
            raise ValueError(
                "Session already has an active round"
            )

        return place_bet(session["balance"], wager)

    def start_round(self, session_id: str, wager: Decimal, rng_mode: str = "hybrid") -> dict:
        wager = validate_money(wager)
        with self._lock:
            self._validate_can_start(session_id, wager)

        crash_point = generate_crash_point(mode=rng_mode)
        crash_time = crash_after_seconds(crash_point)
        distraction = select_distraction()
        with self._lock:
            new_balance = self._validate_can_start(session_id, wager)
            round_id = uuid4().hex
            start_time = self._clock()

            round_data = {
                "round_id": round_id,
                "session_id": session_id,
                "status": "running",
                "wager": wager,
                "crash_point": crash_point,
                "crash_time": crash_time,
                "distraction": distraction,
                "start_time": start_time,
                "cashout_multiplier": None,
                "payout": Decimal("0.00"),
            }

            self.rounds[round_id] = round_data
            session = self.sessions[session_id]
            session["balance"] = new_balance
            session["active_round_id"] = round_id
            self._refresh_round(round_data, start_time)
            return {
                "round_id": round_id,
                "status": round_data["status"],
                "wager": str(wager),
                "balance": str(new_balance),
                "multiplier": 1.0,
                "distraction": (
                    distraction
                    if round_data["status"] == "crashed"
                    else None
                ),
            }

    def get_round_state(self, session_id: str, round_id: str) -> dict:
        with self._lock:
            round_data = self._owned_round(session_id, round_id)
            now = self._clock()
            self._refresh_round(round_data, now)
            status = round_data["status"]
            if status == "running":
                elapsed = now - round_data["start_time"]
                current = multiplier_at(elapsed)
                displayed = math.floor(current * 100) / 100
                return {
                    "status": "running",
                    "multiplier": displayed,
                    "distraction": None,
                }
            
            if status == "crashed":
                return {
                    "status": "crashed",
                    "multiplier": round(round_data["crash_point"], 2),
                    "distraction": round_data["distraction"],
                    "payout": "0.00",
                }

            return {
                "status": "cashed_out",
                "multiplier": round_data["cashout_multiplier"],
                "distraction": None,
                "payout": str(round_data["payout"]),
            }

    def cash_out(self, session_id: str, round_id: str) -> dict:
        with self._lock:
            round_data = self._owned_round(session_id, round_id)
            now = self._clock()
            self._refresh_round(round_data, now)
            status = round_data["status"]
            session = self.sessions[session_id]
            if status == "crashed":
                return {
                    "status": "crashed",
                    "payout": "0.00",
                    "balance": str(session["balance"]),
                }

            if status == "cashed_out":
                return {
                    "status": "cashed_out",
                    "multiplier": round_data[
                        "cashout_multiplier"
                    ],
                    "payout": str(round_data["payout"]),
                    "balance": str(session["balance"]),
                }
            
            elapsed = now - round_data["start_time"]
            current = multiplier_at(elapsed)
            cashout_multiplier = math.floor(current * 100) / 100
            payout = calculate_cashout(wager=round_data["wager"], multiplier=cashout_multiplier,)
            session["balance"] = credit_winnings(session["balance"], payout)
            session["active_round_id"] = None
            round_data["status"] = "cashed_out"
            round_data["cashout_multiplier"] = cashout_multiplier
            round_data["payout"] = payout

            return {
                "status": "cashed_out",
                "multiplier": cashout_multiplier,
                "payout": str(payout),
                "balance": str(session["balance"]),
            }

    def get_balance(self, session_id: str) -> dict:
        with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise KeyError("Session not found")

            return {
                "balance": str(session["balance"])
            }

    def get_round_result(self, session_id: str, round_id: str) -> dict:
        with self._lock:
            round_data = self._owned_round(session_id, round_id)
            self._refresh_round(round_data, self._clock())
            if round_data["status"] == "running":
                return {
                    "status": "running",
                    "result": None,
                }

            return {
                "status": round_data["status"],
                "crash_point": round_data["crash_point"],
                "distraction": round_data["distraction"],
                "payout": str(round_data["payout"]),
            }