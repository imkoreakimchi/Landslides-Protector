from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional


class SegmentState(str, Enum):
    OPEN = "OPEN"
    CAUTION = "CAUTION"
    CLOSED_PENDING = "CLOSED_PENDING"
    CLOSED_CONFIRMED = "CLOSED_CONFIRMED"


class SegmentKind(str, Enum):
    ROAD = "road"
    UNDERPASS = "underpass"
    TRAIL = "trail"
    WALK = "walk"


@dataclass
class Segment:
    id: int
    name: str
    kind: SegmentKind
    hazard_grade: int
    slope: float
    burn_mask: bool
    coords: List[List[float]]
    state: SegmentState = SegmentState.OPEN
    risk_score: float = 0.0
    last_transition: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class FieldCheck:
    segment_id: int
    timestamp: datetime
    device_hash: str
    lat: float
    lng: float
    photo_url: Optional[str]


@dataclass
class RainSample:
    timestamp: datetime
    mm_10min: float

    @property
    def intensity(self) -> float:
        return round(self.mm_10min * 6, 2)


@dataclass
class RainIndices:
    acc15: float
    acc30: float
    acc60: float
    intensity: float


@dataclass
class RouteSubscription:
    user_id: str
    mode: str
    polyline: str
    quiet_hours: Optional[str]
    max_push_per_day: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: int = field(default=0, init=False)


@dataclass
class AlertLog:
    route_id: int
    segment_id: int
    timestamp: datetime
    state_from: SegmentState
    state_to: SegmentState
    sent: bool


def rainfall_zero_for(samples: List[RainSample], duration: timedelta) -> bool:
    if not samples:
        return True
    cutoff = samples[-1].timestamp - duration
    return all(sample.mm_10min <= 0.01 for sample in samples if sample.timestamp >= cutoff)


def normalize(value: float, upper: float) -> float:
    if upper <= 0:
        return 0.0
    return min(max(value / upper, 0.0), 1.0)
