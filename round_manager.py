
import math
import threading

from decimal import Decimal
from time import monotonic
from uuid import uuid4

from crash_engine import (
    generate_crash_point,
    crash_after_seconds,
    multiplier_at,
    select_distraction,
    select_season,
    season_growth_rate,
    MIN_CRASH_SECONDS,
)

from economy import (
    INITIAL_BALANCE,
    validate_money,
    place_bet,
    calculate_cashout,
    credit_winnings,
)

from database.session_repository import from_cents


class RoundManager:
    def __init__(self, clock=monotonic, session_store=None):
        self._session_store = session_store
        self.sessions = {}
        self.rounds = {}
        self._lock = threading.RLock()
        self._clock = clock

    # SESSION MANAGEMENT

    def _session(self, session_id: str) -> dict:
        session = self.sessions.get(session_id)

        if session is None and self._session_store is not None:
            stored = self._session_store.get_session(session_id)

            if stored is not None:
                session = {
                    "balance": stored["balance"],
                    "active_round_id": None,
                }
                self.sessions[session_id] = session

        if session is None:
            raise KeyError("Session not found")

        return session

    def create_session(self) -> dict:
        session_id = uuid4().hex

        with self._lock:
            if self._session_store is not None:
                self._session_store.create_session(
                    session_id,
                    INITIAL_BALANCE,
                )

            self.sessions[session_id] = {
                "balance": INITIAL_BALANCE,
                "active_round_id": None,
            }

        return {
            "session_id": session_id,
            "balance": str(INITIAL_BALANCE),
        }

    # ROUND OWNERSHIP AND RECOVERY

    def _owned_round(
        self,
        session_id: str,
        round_id: str,
    ) -> dict:
        self._session(session_id)

        round_data = self.rounds.get(round_id)

        if round_data is None and self._session_store is not None:
            saved = self._session_store.get_round(
                session_id, round_id
            )

            if saved is not None:
                if saved["status"] == "running":
                    raise ValueError(
                        "Running round cannot resume after a restart"
                    )

                round_data = {
                    "round_id": saved["round_id"],
                    "session_id": saved["session_id"],
                    "status": saved["status"],
                    "wager": from_cents(saved["wager_cents"]),
                    "crash_point": saved["crash_point"],
                    "crash_time": saved["crash_time_seconds"],
                    "distraction": saved["distraction"],

                    "season": saved["season"],
                    "growth_rate": saved["growth_rate"],
                    "rush": bool(saved["rush"]),
                    "lead_in_seconds": saved["lead_in_seconds"],

                    "start_time": None,
                    "cashout_multiplier": saved["cashout_multiplier"],
                    "payout": from_cents(saved["payout_cents"]),
                }

                self.rounds[round_id] = round_data

        if (
            round_data is None
            or round_data["session_id"] != session_id
        ):
            raise KeyError("Round not found for session")

        return round_data

    # ROUND STATE REFRESH

    def _refresh_round(
        self,
        round_data: dict,
        now: float,
    ) -> None:
        if round_data["status"] != "running":
            return

        elapsed = now - round_data["start_time"]

        if elapsed >= round_data["crash_time"]:
            if self._session_store is not None:
                self._session_store.settle_round(
                    round_data["session_id"],
                    round_data["round_id"],
                    "crashed",
                )

            round_data["status"] = "crashed"

            session = self.sessions[
                round_data["session_id"]
            ]

            if (
                session["active_round_id"]
                == round_data["round_id"]
            ):
                session["active_round_id"] = None

    # WAGER VALIDATION

    def _validate_can_start(
        self,
        session_id: str,
        wager: Decimal,
    ) -> Decimal:
        session = self._session(session_id)
        active_id = session["active_round_id"]

        if active_id is not None:
            self._refresh_round(
                self.rounds[active_id],
                self._clock(),
            )

        if session["active_round_id"] is not None:
            raise ValueError(
                "Session already has an active round"
            )

        if self._session_store is not None:
            persisted = self._session_store.get_session(
                session_id
            )

            if persisted is None:
                raise KeyError("Session not found")

            session["balance"] = persisted["balance"]

        return place_bet(session["balance"], wager)

    # START GAME ROUND

    def start_round(
        self,
        session_id: str,
        wager: Decimal,
        rng_mode: str = "hybrid",
    ) -> dict:
        wager = validate_money(wager)

        with self._lock:
            self._validate_can_start(
                session_id, wager
            )

        season = select_season()
        growth_rate, rush = season_growth_rate(season, mode=rng_mode)
        crash_point = generate_crash_point(mode=rng_mode)
        crash_time = crash_after_seconds(crash_point, growth_rate=growth_rate, lead_in_seconds=MIN_CRASH_SECONDS)
        distraction = select_distraction(season)
        with self._lock:
            new_balance = self._validate_can_start(
                session_id, wager
            )

            round_id = uuid4().hex

            if self._session_store is not None:
                new_balance = self._session_store.record_wager(
                    session_id,
                    round_id,
                    wager,
                    crash_point,
                    crash_time,
                    distraction,
                    season=season,
                    growth_rate=growth_rate,
                    rush=rush,
                    lead_in_seconds=MIN_CRASH_SECONDS,
                )

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
                "season": season,
                "growth_rate": growth_rate,
                "rush": rush,
                "lead_in_seconds": MIN_CRASH_SECONDS,
            }

            self.rounds[round_id] = round_data

            session = self.sessions[session_id]
            session["balance"] = new_balance
            session["active_round_id"] = round_id

            self._refresh_round(
                round_data, start_time
            )

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
                "season": season,
                "rush": rush,
                "phase": (
                    "warmup"
                    if round_data["status"] == "running"
                    else "crashed"
                ),
                "warmup_seconds": MIN_CRASH_SECONDS,
                "can_cashout": False,
            }

    # GET LIVE ROUND STATE

    def get_round_state(
        self,
        session_id: str,
        round_id: str,
    ) -> dict:
        with self._lock:
            round_data = self._owned_round(
                session_id, round_id
            )

            now = self._clock()
            self._refresh_round(round_data, now)

            status = round_data["status"]

            if status == "running":
                elapsed = now - round_data["start_time"]
                current = multiplier_at(
                    elapsed,
                    growth_rate=round_data["growth_rate"],
                    lead_in_seconds=round_data["lead_in_seconds"]
                )
                displayed = math.floor(current * 100) / 100
                phase = (
                    "warmup"
                    if elapsed < round_data["lead_in_seconds"]
                    else "active"
                )
                return {
                    "status": "running",
                    "season": round_data["season"],
                    "rush": round_data["rush"],
                    "phase": phase,
                    "warmup_remaining": round(
                        max(
                            0.0,
                            round_data["lead_in_seconds"] - elapsed
                        ),
                        2
                    ),
                    "can_cashout": phase == "active",
                    "multiplier": displayed,
                    "distraction": None,
                }

            if status == "crashed":
                return {
                    "status": "crashed",
                    "multiplier": round(
                        round_data["crash_point"], 2
                    ),
                    "distraction": round_data[
                        "distraction"
                    ],
                    "payout": "0.00",
                }

            if status == "interrupted":
                return {
                    "status": "interrupted",
                    "multiplier": None,
                    "distraction": None,
                    "payout": "0.00",
                }

            return {
                "status": "cashed_out",
                "multiplier": round_data[
                    "cashout_multiplier"
                ],
                "distraction": None,
                "payout": str(
                    round_data["payout"]
                ),
            }

    # CASH OUT

    def cash_out(
        self,
        session_id: str,
        round_id: str,
    ) -> dict:
        with self._lock:
            round_data = self._owned_round(
                session_id, round_id
            )

            now = self._clock()
            self._refresh_round(round_data, now)

            status = round_data["status"]
            session = self._session(session_id)

            if status in {"crashed", "interrupted"}:
                return {
                    "status": status,
                    "payout": "0.00",
                    "balance": self.get_balance(
                        session_id
                    )["balance"],
                }

            if status == "cashed_out":
                return {
                    "status": "cashed_out",
                    "multiplier": round_data[
                        "cashout_multiplier"
                    ],
                    "payout": str(
                        round_data["payout"]
                    ),
                    "balance": self.get_balance(
                        session_id
                    )["balance"],
                }

            elapsed = now - round_data["start_time"]
            if elapsed < round_data["lead_in_seconds"]:
                raise ValueError("Cash-out unavailable during warm-up")

            current = multiplier_at(elapsed, growth_rate=round_data["growth_rate"], lead_in_seconds=round_data["lead_in_seconds"])
            cashout_multiplier = math.floor(current * 100) / 100
            payout = calculate_cashout(round_data["wager"], cashout_multiplier,)
            if self._session_store is not None:
                new_balance = self._session_store.settle_round(
                    session_id,
                    round_id,
                    "cashed_out",
                    payout,
                    cashout_multiplier,
                )
            else:
                new_balance = credit_winnings(
                    session["balance"],
                    payout,
                )

            session["balance"] = new_balance
            session["active_round_id"] = None

            round_data["status"] = "cashed_out"
            round_data[
                "cashout_multiplier"
            ] = cashout_multiplier
            round_data["payout"] = payout

            return {
                "status": "cashed_out",
                "multiplier": cashout_multiplier,
                "payout": str(payout),
                "balance": str(new_balance),
            }

    # PLAYER BALANCE

    def get_balance(self, session_id: str) -> dict:
        with self._lock:
            session = self._session(session_id)

            if self._session_store is not None:
                session["balance"] = (
                    self._session_store.get_session(
                        session_id
                    )["balance"]
                )

            return {
                "balance": str(session["balance"])
            }

    # ROUND RESULT

    def get_round_result(
        self,
        session_id: str,
        round_id: str,
    ) -> dict:
        with self._lock:
            round_data = self._owned_round(
                session_id, round_id
            )

            self._refresh_round(
                round_data, self._clock()
            )

            if round_data["status"] == "running":
                return {
                    "status": "running",
                    "result": None,
                }

            return {
                "status": round_data["status"],
                "season": round_data["season"],
                "rush": round_data["rush"],
                "crash_point": round_data["crash_point"],
                "distraction": round_data["distraction"],
                "payout": str(round_data["payout"]),
            }

    # BET HISTORY

    def get_history(
        self,
        session_id: str,
        limit: int = 30,
    ) -> list[dict]:
        with self._lock:
            self._session(session_id)

            if self._session_store is None:
                return []

            return self._session_store.get_history(
                session_id, limit
            )

    # TRANSACTION HISTORY

    def get_transactions(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict]:
        with self._lock:
            self._session(session_id)

            if self._session_store is None:
                return []

            return self._session_store.get_transactions(
                session_id, limit
            )
