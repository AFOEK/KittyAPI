import json
from decimal import Decimal
from hashlib import sha256
from math import isfinite

from economy import (
    INITIAL_BALANCE,
    MIN_BET,
    MAX_BET,
    validate_money,
    calculate_cashout,
)
from .connection import get_connection


CENTS = Decimal("100")


def to_cents(amount: Decimal) -> int:
    return int(validate_money(amount) * CENTS)


def from_cents(value: int) -> Decimal:
    return (Decimal(value) / CENTS).quantize(
        Decimal("0.01")
    )


class SQLiteSessionStore:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    # SESSION CREATION

    def create_session(
        self,
        session_id: str,
        balance: Decimal = INITIAL_BALANCE,
    ):
        cents = to_cents(balance)
        conn = self._connect()

        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO sessions(
                        session_id, balance_cents
                    ) VALUES (?, ?)
                    """,
                    (session_id, cents),
                )

                if cents:
                    conn.execute(
                        """
                        INSERT INTO credit_transactions(
                            session_id, kind, amount_cents
                        ) VALUES (?, 'initial_grant', ?)
                        """,
                        (session_id, cents),
                    )
        finally:
            conn.close()

    # SESSION RETRIEVAL

    def get_session(self, session_id: str):
        conn = self._connect()

        try:
            row = conn.execute(
                """
                SELECT session_id, balance_cents
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        return {
            "session_id": row["session_id"],
            "balance": from_cents(row["balance_cents"]),
        }

    # ROUND RETRIEVAL

    def get_round(self, session_id: str, round_id: str):
        conn = self._connect()

        try:
            row = conn.execute(
                """
                SELECT *
                FROM rounds
                WHERE session_id = ? AND round_id = ?
                """,
                (session_id, round_id),
            ).fetchone()
        finally:
            conn.close()

        return None if row is None else dict(row)

    # ATOMIC WAGER TRANSACTION

    def record_wager(
        self,
        session_id: str,
        round_id: str,
        wager: Decimal,
        crash_point: float,
        crash_time: float,
        distraction: str,
        season_schedule: list[dict],
        season: str = "spring",
        growth_rate: float = 0.12,
        rush: bool = False,
        lead_in_seconds: float = 3.0,
    ) -> Decimal:
        cents = to_cents(wager)

        if not MIN_BET <= wager <= MAX_BET:
            raise ValueError("Wager outside betting limits")

        if not isfinite(crash_point) or crash_point < 1.0:
            raise ValueError("Invalid crash point")

        if not isfinite(crash_time) or crash_time < 0:
            raise ValueError("Invalid crash time")

        conn = self._connect()

        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")

                cursor = conn.execute(
                    """
                    UPDATE sessions
                    SET balance_cents = balance_cents - ?
                    WHERE session_id = ?
                      AND balance_cents >= ?
                    """,
                    (cents, session_id, cents),
                )

                if cursor.rowcount != 1:
                    raise ValueError(
                        "Insufficient credits or unknown session"
                    )

                conn.execute(
                    """
                    INSERT INTO rounds(
                        round_id,
                        session_id,
                        wager_cents,
                        status,
                        crash_point,
                        crash_time_seconds,
                        distraction,
                        season,
                        growth_rate,
                        rush,
                        lead_in_seconds,
                        season_schedule_json
                    )
                    VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        session_id,
                        cents,
                        crash_point,
                        crash_time,
                        distraction,
                        season,
                        growth_rate,
                        int(rush),
                        lead_in_seconds,
                        json.dumps(season_schedule, separators=(",", ":"))
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO credit_transactions(
                        session_id,
                        round_id,
                        kind,
                        amount_cents
                    )
                    VALUES (?, ?, 'wager', ?)
                    """,
                    (session_id, round_id, -cents),
                )

                row = conn.execute(
                    """
                    SELECT balance_cents
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()

                balance = row["balance_cents"]

            return from_cents(balance)

        finally:
            conn.close()

    # ATOMIC CASH-OUT / CRASH SETTLEMENT

    def settle_round(
        self,
        session_id: str,
        round_id: str,
        status: str,
        payout: Decimal = Decimal("0.00"),
        multiplier: float | None = None,
    ) -> Decimal:
        if status not in {"cashed_out", "crashed"}:
            raise ValueError("Invalid settlement status")

        cents = to_cents(payout)

        if status == "crashed":
            if cents or multiplier is not None:
                raise ValueError(
                    "Crashed round cannot pay winnings"
                )
        else:
            if (
                multiplier is None
                or not isfinite(multiplier)
                or multiplier < 1
            ):
                raise ValueError("Invalid multiplier")

            if cents <= 0:
                raise ValueError("Payout must be positive")

        conn = self._connect()

        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")

                row = conn.execute(
                    """
                    SELECT status, wager_cents
                    FROM rounds
                    WHERE session_id = ?
                      AND round_id = ?
                    """,
                    (session_id, round_id),
                ).fetchone()

                if row is None or row["status"] != "running":
                    raise ValueError(
                        "Round already settled or not found"
                    )

                if status == "cashed_out":
                    expected = calculate_cashout(
                        from_cents(row["wager_cents"]),
                        multiplier,
                    )

                    if payout != expected:
                        raise ValueError(
                            "Payout does not match wager and multiplier"
                        )

                conn.execute(
                    """
                    UPDATE rounds
                    SET status = ?,
                        payout_cents = ?,
                        cashout_multiplier = ?,
                        finished_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                      AND round_id = ?
                      AND status = 'running'
                    """,
                    (
                        status,
                        cents,
                        multiplier,
                        session_id,
                        round_id,
                    ),
                )

                if cents:
                    conn.execute(
                        """
                        UPDATE sessions
                        SET balance_cents = balance_cents + ?
                        WHERE session_id = ?
                        """,
                        (cents, session_id),
                    )

                    conn.execute(
                        """
                        INSERT INTO credit_transactions(
                            session_id,
                            round_id,
                            kind,
                            amount_cents
                        )
                        VALUES (?, ?, 'payout', ?)
                        """,
                        (session_id, round_id, cents),
                    )

                row = conn.execute(
                    """
                    SELECT balance_cents
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()

                balance = row["balance_cents"]

            return from_cents(balance)

        finally:
            conn.close()

    # SERVER RESTART RECOVERY

    def recover_interrupted_rounds(self) -> int:
        """
        Refund previously running rounds once.
        Call during application startup only.
        """
        conn = self._connect()

        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")

                pending = conn.execute(
                    """
                    SELECT round_id, session_id, wager_cents
                    FROM rounds
                    WHERE status = 'running'
                    """
                ).fetchall()

                for record in pending:
                    rid = record["round_id"]
                    sid = record["session_id"]
                    cents = record["wager_cents"]

                    conn.execute(
                        """
                        UPDATE rounds
                        SET status = 'interrupted',
                            finished_at = CURRENT_TIMESTAMP
                        WHERE round_id = ?
                          AND status = 'running'
                        """,
                        (rid,),
                    )

                    conn.execute(
                        """
                        UPDATE sessions
                        SET balance_cents = balance_cents + ?
                        WHERE session_id = ?
                        """,
                        (cents, sid),
                    )

                    conn.execute(
                        """
                        INSERT INTO credit_transactions(
                            session_id,
                            round_id,
                            kind,
                            amount_cents
                        )
                        VALUES (?, ?, 'refund', ?)
                        """,
                        (sid, rid, cents),
                    )

            return len(pending)

        finally:
            conn.close()

    # PLAYER BET HISTORY

    def get_history(
        self,
        session_id: str,
        limit: int = 30,
    ) -> list[dict]:
        conn = self._connect()

        try:
            rows = conn.execute(
                """
                SELECT
                    round_id,
                    status,
                    wager_cents,
                    payout_cents,
                    cashout_multiplier,
                    started_at,
                    finished_at
                FROM rounds
                WHERE session_id = ?
                ORDER BY started_at DESC, rowid DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "round_id": row["round_id"],
                "status": row["status"],
                "wager": str(
                    from_cents(row["wager_cents"])
                ),
                "payout": str(
                    from_cents(row["payout_cents"])
                ),
                "net_profit": (
                    str(
                        from_cents(
                            row["payout_cents"]
                            - row["wager_cents"]
                        )
                    )
                    if row["status"] in {
                        "crashed",
                        "cashed_out",
                    }
                    else None
                ),
                "cashout_multiplier": row[
                    "cashout_multiplier"
                ],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
            for row in rows
        ]

    # PLAYER CREDIT TRANSACTIONS

    def get_transactions(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict]:
        conn = self._connect()

        try:
            rows = conn.execute(
                """
                SELECT
                    event_id,
                    round_id,
                    kind,
                    amount_cents,
                    created_at
                FROM credit_transactions
                WHERE session_id = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "event_id": row["event_id"],
                "round_id": row["round_id"],
                "kind": row["kind"],
                "amount": str(
                    from_cents(row["amount_cents"])
                ),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # PUBLIC LEADERBOARD

    def get_leaderboard(
        self,
        limit: int = 10,
    ) -> list[dict]:
        conn = self._connect()

        try:
            rows = conn.execute(
                """
                SELECT
                    session_id,
                    COUNT(*) AS games,
                    SUM(
                        CASE WHEN status = 'cashed_out'
                        THEN 1 ELSE 0 END
                    ) AS wins,
                    SUM(
                        payout_cents - wager_cents
                    ) AS net_cents
                FROM rounds
                WHERE status IN ('cashed_out', 'crashed')
                GROUP BY session_id
                ORDER BY net_cents DESC, games DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "rank": index,
                "player": "Cat-" + sha256(
                    row["session_id"].encode()
                ).hexdigest()[:8],
                "games": row["games"],
                "wins": row["wins"],
                "net_profit": str(
                    from_cents(row["net_cents"])
                ),
            }
            for index, row in enumerate(rows, start=1)
        ]
