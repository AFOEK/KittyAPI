import math
import secrets
import hashlib
import hmac

from randomness import generate_random

HOUSE_EDGE = 0.04
MAX_MULTIPLIER = 100.0

# Retained for compatibility with old standalone math tests.
GROWTH_RATE = 0.18

# No crash in the first 3 seconds.
MIN_CRASH_SECONDS = 3.0

SEASONS = ("spring", "summer", "fall", "winter")

SEASON_DURATION_RANGES = {
    "spring": (2.5, 4.0),
    "summer": (1.5, 3.0),
    "fall":   (3.5, 6.0),
    "winter": (6.0, 10.0),
}

SEASON_GROWTH = {
    "spring": 0.12,
    "summer": 0.13,
    "fall": 0.12,
    "winter": 0.085,
}

SUMMER_RUSH_CHANCE = 0.40
SUMMER_RUSH_GROWTH = 0.20

DISTRACTION_WEIGHTS = {
    "spring": {
        "butterfly": 50,
        "fish": 15,
        "sleep": 10,
        "yarn": 10,
        "laser": 10,
        "cardboard_box": 5,
    },
    "summer": {
        "fish": 30,
        "butterfly": 25,
        "laser": 20,
        "yarn": 10,
        "sleep": 10,
        "cardboard_box": 5,
    },
    "fall": {
        "yarn": 50,
        "fish": 10,
        "sleep": 15,
        "butterfly": 10,
        "laser": 10,
        "cardboard_box": 5,
    },
    "winter": {
        "sleep": 45,
        "cardboard_box": 25,
        "fish": 10,
        "yarn": 10,
        "butterfly": 5,
        "laser": 5,
    },
}


def validate_season(season: str) -> None:
    if season not in SEASONS:
        raise ValueError(f"Unknown season: {season}")

def generate_round_seed(mode="hybrid") -> bytes:
    result = generate_random(mode=mode, qubits=6, samples=6)
    quantum_hybrid_bytes = result["integer"].to_bytes((result["bits"] + 7) // 8, "big")
    secure_bytes = secrets.token_bytes(32)
    return hashlib.sha256(secure_bytes + quantum_hybrid_bytes).digest()

def seeded_uniform(seed: bytes, label: str) -> float:
    digest = hmac.new(
        seed,
        label.encode("utf-8"),
        hashlib.sha256
    ).digest()

    number = int.from_bytes(digest[:8], "big") >> 12

    return (number + 0.5) / (1 << 52)

def generate_season_schedule(seed: bytes) -> list[dict]:

    seasons = ("spring", "summer", "fall", "winter")

    horizon = (
        math.log(MAX_MULTIPLIER)
        / min(SEASON_GROWTH.values())
        + 1.0
    )

    schedule = []
    elapsed = 0.0
    index = 0

    while elapsed < horizon:
        season = seasons[index % 4]

        low, high = SEASON_DURATION_RANGES[season]

        u = seeded_uniform(
            seed, f"duration:{index}"
        )

        duration = low + (high - low) * u

        rush = (
            season == "summer"
            and seeded_uniform(
                seed, f"rush:{index}"
            ) < SUMMER_RUSH_CHANCE
        )

        growth = (
            SUMMER_RUSH_GROWTH
            if rush
            else SEASON_GROWTH[season]
        )

        end = min(elapsed + duration, horizon)

        schedule.append({
            "season": season,
            "start": elapsed,
            "end": end,
            "growth_rate": growth,
            "rush": rush,
        })

        elapsed = end
        index += 1

    return schedule

def seasonal_multiplier_at(
    elapsed: float,
    schedule: list[dict],
    warmup: float = MIN_CRASH_SECONDS
) -> float:

    active = max(0.0, elapsed - warmup)
    exponent = 0.0

    for segment in schedule:
        duration = max(
            0.0,
            min(active, segment["end"])
            - segment["start"]
        )

        exponent += segment["growth_rate"] * duration

    return math.exp(exponent)

def seasonal_crash_time(
    crash_point: float,
    schedule: list[dict],
    warmup: float = MIN_CRASH_SECONDS
) -> float:

    if not 1.0 <= crash_point <= MAX_MULTIPLIER:
        raise ValueError("Invalid crash point")

    remaining = math.log(crash_point)

    if remaining == 0.0:
        return warmup

    for segment in schedule:
        growth = segment["growth_rate"]

        duration = (
            segment["end"] - segment["start"]
        )

        available_growth = growth * duration

        if remaining <= available_growth:
            return (
                warmup
                + segment["start"]
                + remaining / growth
            )

        remaining -= available_growth

    raise RuntimeError(
        "Season schedule does not reach crash point"
    )

def current_season(
    elapsed: float,
    schedule: list[dict],
    warmup: float = MIN_CRASH_SECONDS
) -> dict:

    active = max(0.0, elapsed - warmup)

    for segment in schedule:
        if active < segment["end"]:
            return segment

    return schedule[-1]


def generate_round_plan(mode="hybrid") -> dict:

    seed = generate_round_seed(mode)

    schedule = generate_season_schedule(seed)

    u = seeded_uniform(seed, "crash")
    crash_point = crash_from_uniform(u)

    crash_time = seasonal_crash_time(
        crash_point, schedule
    )

    crash_season = current_season(
        crash_time, schedule
    )["season"]

    distraction = select_distraction(crash_season)

    return {
        "crash_point": crash_point,
        "crash_time": crash_time,
        "schedule": schedule,
        "distraction": distraction,
        "warmup": MIN_CRASH_SECONDS,
        "seed_commitment": hashlib.sha256(
            seed
        ).hexdigest(),
    }

def select_season() -> str:
    return secrets.choice(SEASONS)

def season_growth_rate(
    season: str,
    mode: str = "hybrid"
) -> tuple[float, bool]:

    validate_season(season)

    if season != "summer":
        return SEASON_GROWTH[season], False

    # An independent simulated-quantum/hybrid RNG draw
    # determines whether Summer Rush activates.
    result = generate_random(
        mode=mode,
        qubits=6,
        samples=6
    )

    rush = result["normalized"] < SUMMER_RUSH_CHANCE

    growth_rate = (
        SUMMER_RUSH_GROWTH
        if rush
        else SEASON_GROWTH["summer"]
    )

    return growth_rate, rush


def select_distraction(
    season: str = "spring"
) -> str:

    validate_season(season)

    weights = DISTRACTION_WEIGHTS[season]
    roll = secrets.randbelow(sum(weights.values()))

    for event, weight in weights.items():
        if roll < weight:
            return event
        roll -= weight

    raise RuntimeError("Invalid distraction weights")


def crash_from_uniform(
    u: float,
    house_edge: float = HOUSE_EDGE,
    max_multiplier: float = MAX_MULTIPLIER
) -> float:

    if not 0.0 < u < 1.0:
        raise ValueError("u must be between 0 and 1")

    if not 0.0 <= house_edge < 1.0:
        raise ValueError("Invalid house edge")

    if max_multiplier <= 1.0:
        raise ValueError(
            "Maximum multiplier must exceed 1"
        )

    rtp = 1.0 - house_edge

    crash = rtp / u

    return max(
        1.0,
        min(crash, max_multiplier)
    )


def generate_crash_point(
    mode: str = "hybrid"
) -> float:

    result = generate_random(
        mode=mode,
        qubits=6,
        samples=6
    )

    return crash_from_uniform(result["normalized"])


def multiplier_at(
    elapsed_seconds: float,
    growth_rate: float = GROWTH_RATE,
    lead_in_seconds: float = 0.0
) -> float:

    if elapsed_seconds < 0:
        raise ValueError(
            "Elapsed time cannot be negative"
        )

    if growth_rate <= 0:
        raise ValueError(
            "Growth rate must be positive"
        )

    if lead_in_seconds < 0:
        raise ValueError(
            "Lead-in cannot be negative"
        )

    active_seconds = max(
        0.0,
        elapsed_seconds - lead_in_seconds
    )

    return math.exp(
        growth_rate * active_seconds
    )


def crash_after_seconds(
    crash_point: float,
    growth_rate: float = GROWTH_RATE,
    lead_in_seconds: float = 0.0
) -> float:

    if crash_point < 1.0:
        raise ValueError(
            "Crash point cannot be below 1"
        )

    if growth_rate <= 0:
        raise ValueError(
            "Growth rate must be positive"
        )

    if lead_in_seconds < 0:
        raise ValueError(
            "Lead-in cannot be negative"
        )

    return (
        lead_in_seconds
        + math.log(crash_point) / growth_rate
    )