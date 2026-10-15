CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    balance_cents INTEGER NOT NULL
        CHECK(balance_cents >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rounds (
    round_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,

    wager_cents INTEGER NOT NULL CHECK(wager_cents > 0),
    payout_cents INTEGER NOT NULL DEFAULT 0,

    status TEXT NOT NULL CHECK (
        status IN ('running', 'crashed', 'cashed_out', 'interrupted')
    ),

    crash_point REAL NOT NULL,
    crash_time_seconds REAL NOT NULL,
    distraction TEXT,

    cashout_multiplier REAL,

    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,

    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);