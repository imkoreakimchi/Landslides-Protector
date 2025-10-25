from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List, Tuple

from .models import (
    AlertLog,
    FieldCheck,
    RainIndices,
    RainSample,
    RouteSubscription,
    Segment,
    SegmentKind,
    SegmentState,
    normalize,
    rainfall_zero_for,
)


QR_CONFIRMATIONS_REQUIRED = 2


class InMemoryStore:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.segments: Dict[int, Segment] = {
            1: Segment(
                id=1,
                name="Bukhan Trail 1",
                kind=SegmentKind.TRAIL,
                hazard_grade=4,
                slope=18.0,
                burn_mask=False,
                coords=[[126.9780, 37.5665], [126.9790, 37.5680], [126.9805, 37.5695]],
            ),
            2: Segment(
                id=2,
                name="Hangang Riverside",
                kind=SegmentKind.WALK,
                hazard_grade=2,
                slope=2.0,
                burn_mask=False,
                coords=[[126.961, 37.528], [126.964, 37.53], [126.968, 37.532]],
            ),
            3: Segment(
                id=3,
                name="Yangjae Underpass",
                kind=SegmentKind.UNDERPASS,
                hazard_grade=5,
                slope=0.5,
                burn_mask=True,
                coords=[[127.031, 37.485], [127.034, 37.486]],
            ),
        }

        self.rain_history: Dict[int, Deque[RainSample]] = defaultdict(lambda: deque(maxlen=36))
        for seg_id in self.segments:
            self.rain_history[seg_id].append(RainSample(timestamp=now - timedelta(minutes=10), mm_10min=0.5))
            self.rain_history[seg_id].append(RainSample(timestamp=now, mm_10min=1.0))

        self.field_checks: Dict[int, List[FieldCheck]] = defaultdict(list)
        self.routes: Dict[int, RouteSubscription] = {}
        self.alerts: List[AlertLog] = []
        self._route_seq = 1

    # ---------------- Rainfall -----------------
    def push_rain_sample(self, segment_id: int, mm_10min: float) -> RainIndices:
        samples = self.rain_history[segment_id]
        ts = datetime.now(timezone.utc)
        samples.append(RainSample(timestamp=ts, mm_10min=mm_10min))
        return self._compute_indices(samples)

    def get_rain_indices(self, segment_id: int) -> RainIndices:
        return self._compute_indices(self.rain_history[segment_id])

    def _compute_indices(self, samples: Deque[RainSample]) -> RainIndices:
        acc15 = sum(s.mm_10min for s in samples if s.timestamp >= datetime.now(timezone.utc) - timedelta(minutes=15))
        acc30 = sum(s.mm_10min for s in samples if s.timestamp >= datetime.now(timezone.utc) - timedelta(minutes=30))
        acc60 = sum(s.mm_10min for s in samples if s.timestamp >= datetime.now(timezone.utc) - timedelta(minutes=60))
        latest = samples[-1] if samples else RainSample(timestamp=datetime.now(timezone.utc), mm_10min=0.0)
        return RainIndices(acc15=round(acc15, 2), acc30=round(acc30, 2), acc60=round(acc60, 2), intensity=latest.intensity)

    # ---------------- Segment States -----------------
    def set_segment_state(self, segment_id: int, state: SegmentState, risk_score: float) -> None:
        segment = self.segments[segment_id]
        previous = segment.state
        segment.state = state
        segment.risk_score = round(risk_score, 3)
        segment.last_transition = datetime.now(timezone.utc)
        if previous != state:
            self.alerts.append(
                AlertLog(
                    route_id=0,
                    segment_id=segment_id,
                    timestamp=segment.last_transition,
                    state_from=previous,
                    state_to=state,
                    sent=False,
                )
            )

    def get_segments(self, *, kind: List[SegmentKind] | None = None, state: List[SegmentState] | None = None) -> List[Segment]:
        results = list(self.segments.values())
        if kind:
            results = [s for s in results if s.kind in kind]
        if state:
            results = [s for s in results if s.state in state]
        return results

    # ---------------- Field Checks -----------------
    def add_field_check(self, check: FieldCheck) -> int:
        checks = self.field_checks[check.segment_id]
        checks.append(check)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=90)
        recent = [c for c in checks if c.timestamp >= cutoff]
        return len(recent)

    def recent_field_checks(self, segment_id: int) -> List[FieldCheck]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
        return [c for c in self.field_checks[segment_id] if c.timestamp >= cutoff]

    # ---------------- Routes & Alerts -----------------
    def add_route(self, route: RouteSubscription) -> RouteSubscription:
        route.id = self._route_seq
        self._route_seq += 1
        self.routes[route.id] = route
        return route

    def list_routes(self) -> List[RouteSubscription]:
        return list(self.routes.values())

    # ---------------- Risk Logic -----------------
    def evaluate_risk(self, segment_id: int) -> Tuple[float, RainIndices]:
        segment = self.segments[segment_id]
        indices = self.get_rain_indices(segment_id)

        w1, w2, w3, w4, w5, w6 = 0.35, 0.25, 0.15, 0.1, 0.1, 0.05
        score = (
            w1 * normalize(segment.hazard_grade, 5)
            + w2 * normalize(indices.acc30, 20)
            + w3 * normalize(indices.intensity, 60)
            + w4 * (1.0 if segment.burn_mask else 0.0)
            + w5 * normalize(segment.slope, 30)
            + w6 * {
                SegmentKind.TRAIL: 1.0,
                SegmentKind.UNDERPASS: 0.8,
                SegmentKind.ROAD: 0.6,
                SegmentKind.WALK: 0.4,
            }[segment.kind]
        )

        return round(score, 3), indices

    def should_demote(self, segment_id: int) -> bool:
        samples = list(self.rain_history[segment_id])
        return rainfall_zero_for(samples, timedelta(minutes=60))


store = InMemoryStore()
