
from decimal import Decimal
from math import isfinite

from .connection import get_connection
from economy import MIN_BET, MAX_BET, validate_money


class SQLiteSessionStore:

    # ----------------------------------------
    # CREATE SESSION
    # ----------------------------------------

    def create_session(
        self,
        session_id: str,
        balance: Decimal
    ):
        balance = validate_money(balance)
        balance_cents = int(balance * 100)

        conn = get_connection()

        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id,
                        balance_cents
                    )
                    VALUES (?, ?)
                    """,
                    (session_id, balance_cents)
                )
        finally:
            conn.close()

    # ----------------------------------------
    # GET SESSION
    # ----------------------------------------

    def get_session(self, session_id: str):
        conn = get_connection()

        try:
            row = conn.execute(
                """
                SELECT session_id, balance_cents
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,)
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        balance = (
            Decimal(row["balance_cents"])
            / Decimal("100")
        )

        return {
            "session_id": row["session_id"],
            "balance": balance.quantize(
                Decimal("0.01")
            )
        }

    # ----------------------------------------
    # RECORD WAGER
    # ----------------------------------------

    def record_wager(
        self,
        session_id: str,
        round_id: str,
        wager: Decimal,
        crash_point: float,
        crash_time: float,
        distraction: str
    ) -> Decimal:

        # Validate wager
        wager = validate_money(wager)

        if not MIN_BET <= wager <= MAX_BET:
            raise ValueError(
                "Wager outside betting limits"
            )

        if not isfinite(crash_point) or crash_point < 1.0:
            raise ValueError("Invalid crash point")

        if not isfinite(crash_time) or crash_time < 0:
            raise ValueError("Invalid crash time")

        wager_cents = int(wager * 100)

        conn = get_connection()

        try:
            with conn:
                # Begin atomic write transaction
                conn.execute("BEGIN IMMEDIATE")

                # Deduct wager
                cursor = conn.execute(
                    """
                    UPDATE sessions
                    SET balance_cents = balance_cents - ?
                    WHERE session_id = ?
                      AND balance_cents >= ?
                    """,
                    (
                        wager_cents,
                        session_id,
                        wager_cents
                    )
                )

                if cursor.rowcount != 1:
                    raise ValueError(
                        "Insufficient credits or unknown session"
                    )

                # Insert new round
                conn.execute(
                    """
                    INSERT INTO rounds (
                        round_id,
                        session_id,
                        wager_cents,
                        status,
                        crash_point,
                        crash_time_seconds,
                        distraction
                    )
                    VALUES (?, ?, ?, 'running', ?, ?, ?)
                    """,
                    (
                        round_id,
                        session_id,
                        wager_cents,
                        crash_point,
                        crash_time,
                        distraction
                    )
                )

                # Get updated balance
                row = conn.execute(
                    """
                    SELECT balance_cents
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,)
                ).fetchone()

                new_balance_cents = row["balance_cents"]

            return (
                Decimal(new_balance_cents)
                / Decimal("100")
            ).quantize(Decimal("0.01"))

        finally:
            conn.close()

    # ----------------------------------------
    # SETTLE ROUND
    # ----------------------------------------

    def settle_round(
        self,
        session_id: str,
        round_id: str,
        status: str,
        payout: Decimal = Decimal("0.00"),
        multiplier: float | None = None
    ) -> Decimal:

        # Validate settlement status
        if status not in {"crashed", "cashed_out"}:
            raise ValueError(
                "Invalid settlement status"
            )

        payout = validate_money(payout)

        # Crashed rounds cannot pay winnings
        if status == "crashed":
            if payout != 0 or multiplier is not None:
                raise ValueError(
                    "Crashed rounds cannot pay winnings"
                )

        # Validate cash-out parameters
        if status == "cashed_out":
            if (
                payout <= 0
                or multiplier is None
                or not isfinite(multiplier)
                or multiplier < 1.0
            ):
                raise ValueError(
                    "Invalid cash-out settlement"
                )

        payout_cents = int(payout * 100)

        conn = get_connection()

        try:
            with conn:
                # Begin atomic write transaction
                conn.execute("BEGIN IMMEDIATE")

                # Update round status exactly once
                cursor = conn.execute(
                    """
                    UPDATE rounds
                    SET status = ?,
                        payout_cents = ?,
                        cashout_multiplier = ?,
                        finished_at = CURRENT_TIMESTAMP
                    WHERE round_id = ?
                      AND session_id = ?
                      AND status = 'running'
                    """,
                    (
                        status,
                        payout_cents,
                        multiplier,
                        round_id,
                        session_id
                    )
                )

                if cursor.rowcount != 1:
                    raise ValueError(
                        "Round already settled or not found"
                    )

                # Credit payout for successful cash-out
                if payout_cents > 0:
                    cursor = conn.execute(
                        """
                        UPDATE sessions
                        SET balance_cents = balance_cents + ?
                        WHERE session_id = ?
                        """,
                        (
                            payout_cents,
                            session_id
                        )
                    )

                    if cursor.rowcount != 1:
                        raise ValueError(
                            "Session not found"
                        )

                # Retrieve final balance
                row = conn.execute(
                    """
                    SELECT balance_cents
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,)
                ).fetchone()

                if row is None:
                    raise ValueError(
                        "Session not found"
                    )

                balance_cents = row["balance_cents"]

            # Return balance after transaction commits
            return (
                Decimal(balance_cents)
                / Decimal("100")
            ).quantize(Decimal("0.01"))

        finally:
            conn.close()
