from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import BackgroundTasks

from .data_store import QR_CONFIRMATIONS_REQUIRED, store
from .models import FieldCheck, RainIndices, SegmentKind, SegmentState


TAU_CAUTION = 0.45
TAU_CLOSED = 0.65


def evaluate_and_transition(segment_id: int) -> None:
    score, indices = store.evaluate_risk(segment_id)

    if score >= TAU_CLOSED:
        next_state = SegmentState.CLOSED_PENDING
        confirmations = len(store.recent_field_checks(segment_id))
        if confirmations >= QR_CONFIRMATIONS_REQUIRED:
            next_state = SegmentState.CLOSED_CONFIRMED
    elif score >= TAU_CAUTION:
        next_state = SegmentState.CAUTION
    else:
        next_state = SegmentState.OPEN

    if next_state != SegmentState.OPEN and store.should_demote(segment_id):
        next_state = SegmentState.CAUTION if next_state != SegmentState.CAUTION else SegmentState.OPEN

    store.set_segment_state(segment_id, next_state, score)


def refresh_all_segments() -> None:
    for segment_id in store.segments:
        evaluate_and_transition(segment_id)


def ingest_rainfall(segment_id: int, mm_10min: float) -> RainIndices:
    indices = store.push_rain_sample(segment_id, mm_10min)
    evaluate_and_transition(segment_id)
    return indices


def register_field_check(segment_id: int, device_hash: str, lat: float, lng: float, photo_url: str | None) -> int:
    check = FieldCheck(
        segment_id=segment_id,
        timestamp=datetime.now(timezone.utc),
        device_hash=device_hash,
        lat=lat,
        lng=lng,
        photo_url=photo_url,
    )
    count = store.add_field_check(check)
    evaluate_and_transition(segment_id)
    return count


def auto_release_segments() -> None:
    for segment_id in store.segments:
        segment = store.segments[segment_id]
        if segment.state in (SegmentState.CLOSED_PENDING, SegmentState.CLOSED_CONFIRMED) and store.should_demote(segment_id):
            store.set_segment_state(segment_id, SegmentState.CAUTION, segment.risk_score)
        elif segment.state == SegmentState.CAUTION and store.should_demote(segment_id):
            store.set_segment_state(segment_id, SegmentState.OPEN, segment.risk_score)


class Scheduler:
    def __init__(self, background: BackgroundTasks):
        self.background = background

    def enqueue_refresh(self) -> None:
        self.background.add_task(refresh_all_segments)

    def enqueue_release(self) -> None:
        self.background.add_task(auto_release_segments)


__all__ = [
    "Scheduler",
    "auto_release_segments",
    "evaluate_and_transition",
    "ingest_rainfall",
    "register_field_check",
]
