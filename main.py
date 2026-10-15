import os

from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

from round_manager import RoundManager

class StartRoundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wager: Decimal = Field(gt=0, description="Wager in virtual credits",)

def game_call(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

app = FastAPI(
    title="Quantum Cat Crash API",
    description=("Quantum-inspired casino crash game using Qiskit Aer and hybrid randomness."), 
    version="0.1.0"
)

manager = RoundManager()
GAME_RNG_MODE = os.getenv("GAME_RNG_MODE", "hybrid").lower()
if GAME_RNG_MODE not in {"hybrid", "secure"}:
    raise RuntimeError("Gameplay RNG must be 'hybrid' or 'secure'")

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:3000,"
        "http://localhost:8080"
    ).split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Session-ID"],
)

SessionHeader = Annotated[str, Header(alias="X-Session-ID", min_length=1)]

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "game": "Quantum Cat Crash",
        "version": "0.1.0",
        "rng_mode": GAME_RNG_MODE,
    }

@app.post("/api/sessions", status_code=201)
def create_session():
    return manager.create_session()

@app.post("/api/rounds", status_code=201)
def start_round(payload: StartRoundRequest, session_id: SessionHeader):
    return game_call(manager.start_round, session_id, payload.wager, rng_mode=GAME_RNG_MODE)

@app.get("/api/rounds/{round_id}/state")
def get_round_state(round_id: str, session_id: SessionHeader):
    return game_call(manager.get_round_state, session_id, round_id)

@app.post("/api/rounds/{round_id}/cashout")
def cash_out(round_id: str, session_id: SessionHeader):
    return game_call(manager.cash_out, session_id, round_id)

@app.get("/api/rounds/{round_id}/result")
def get_round_result(round_id: str, session_id: SessionHeader):
    return game_call(manager.get_round_result, session_id, round_id)

@app.get("/api/player/balance")
def get_balance(session_id: SessionHeader):
    return game_call(manager.get_balance, session_id)