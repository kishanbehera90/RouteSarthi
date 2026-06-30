"""Pydantic schemas mirroring frontend/API_CONTRACT.md.

These are the canonical response shapes the engine must produce. In the
scaffold step the endpoints return seed dicts directly (byte-for-byte parity
with the frontend mock); these models document the contract and will be used
for validation once responses are computed from real data.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    # Allow populating by field name while serialising with the contract's
    # JSON keys (notably the reserved word "from").
    model_config = ConfigDict(populate_by_name=True)


class CityRef(_Base):
    code: str
    name: str
    state: str | None = None


class Hub(_Base):
    code: str
    name: str


class DelayProfile(_Base):
    avgMins: int
    onTimePct: int


class Leg(_Base):
    id: str
    mode: str  # 'train' | 'bus' | 'cab' | 'connection'
    # moving-leg fields
    name: str | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    depart: str | None = None
    arrive: str | None = None
    durationMins: int | None = None
    fareInr: int | None = None
    confirmation: str | None = None
    waitlistPosition: int | None = None
    clearProbabilityPct: int | None = None
    delayProfile: DelayProfile | None = None
    # connection-leg fields
    connectionSafetyPct: int | None = None
    bufferMins: int | None = None
    note: str | None = None


class Route(_Base):
    id: str
    type: str  # 'direct' | 'cross-origin'
    totalTimeMins: int
    totalFareInr: int
    reliability: int
    confirmation: str
    waitlistPosition: int | None = None
    confirmationPct: int | None = None
    clearProbabilityPct: int | None = None
    hub: Hub | None = None
    why: str = ""
    planB: str | None = None
    legs: list[Leg] = []


class ReasoningDirect(_Base):
    confirmability: int
    note: str


class HubScanned(_Base):
    name: str
    dailyTrains: int
    confirmPct: int
    winner: bool | None = None
    note: str | None = None


class Reasoning(_Base):
    direct: ReasoningDirect
    hubsScanned: list[HubScanned]


class Corridor(_Base):
    id: str
    from_: CityRef = Field(alias="from")
    to: CityRef
    tagline: str
    reasoning: Reasoning | None = None


class RoutesResponse(_Base):
    corridor: Corridor | None = None
    routes: list[Route] = []
