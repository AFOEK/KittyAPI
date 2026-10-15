import math
import secrets

from decimal import Decimal, ROUND_HALF_UP
from randomness import generate_random

HOUSE_EDGE = 0.04
MAX_MULTIPLIER = 100.0
GROWTH_RATE = 0.18

DISTRACTIONS = [
    "fish",
    "sleep",
    "yarn",
    # "butterfly",
    # "laser",
    # "cardboard_box",
]

def crash_from_uniform(u: float, house_edge: float = HOUSE_EDGE, max_multiplier: float = MAX_MULTIPLIER) -> float:
    if not 0.0 < u < 1.0:
        raise ValueError("u must be between 0 and 1")

    if not 0.0 <= house_edge < 1.0:
        raise ValueError("Invalid house edge")

    if max_multiplier <= 1.0:
        raise ValueError("Maximum multiplier must exceed 1")

    rtp = 1.0 - house_edge
    crash = rtp / u
    return max(1.0, min(crash, max_multiplier))

def generate_crash_point(mode: str = "hybrid") -> float:
    result = generate_random(mode=mode, qubits=6, samples=6)
    u = result["normalized"]
    return crash_from_uniform(u)

def multiplier_at(elapsed_seconds: float, growth_rate: float = GROWTH_RATE) -> float:
    if elapsed_seconds < 0:
        raise ValueError("Elapsed time cannot be negative")

    if growth_rate <= 0:
        raise ValueError("Growth rate must be positive")

    return math.exp(growth_rate * elapsed_seconds)

def crash_after_seconds(crash_point: float, growth_rate: float = GROWTH_RATE) -> float:
    if crash_point < 1.0:
        raise ValueError("Crash point cannot be below 1")

    if growth_rate <= 0:
        raise ValueError("Growth rate must be positive")

    return math.log(crash_point) / growth_rate

def select_distraction() -> str:
    return secrets.choice(DISTRACTIONS)