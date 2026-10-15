import time
from crash_engine import crash_after_seconds, multiplier_at

def get_round_state(round_data: dict) -> dict:
    elapsed = time.monotonic() - round_data["start_time"]
    crash_time = crash_after_seconds(round_data["crash_point"])
    if elapsed >= crash_time:
        return {
            "status": "crashed",
            "multiplier": round(
                round_data["crash_point"], 2
            ),
            "distraction": round_data["distraction"]
        }

    return {
        "status": "running",
        "multiplier": round(multiplier_at(elapsed), 2),
        "distraction": None
    }