from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .data_store import store
from .models import (
    RainIndices,
    RouteSubscription,
    Segment,
    SegmentKind,
    SegmentState,
)
from .risk_engine import Scheduler, ingest_rainfall, register_field_check
from .tiles import render_tile

app = FastAPI(title="Landslide Protector API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
,
    allow_headers=["*"]
)


def scheduler_dep(background: BackgroundTasks) -> Scheduler:
    return Scheduler(background)


class SegmentResponse(BaseModel):
    id: int
    name: str
    kind: SegmentKind
    hazard_grade: int
    slope: float
    burn_mask: bool
    coords: List[List[float]]
    state: SegmentState
    risk_score: float

    @classmethod
    def from_segment(cls, segment: Segment) -> "SegmentResponse":
        return cls(
            id=segment.id,
            name=segment.name,
            kind=segment.kind,
            hazard_grade=segment.hazard_grade,
            slope=segment.slope,
            burn_mask=segment.burn_mask,
            coords=segment.coords,
            state=segment.state,
            risk_score=segment.risk_score,
        )


class RainIndicesModel(BaseModel):
    acc15: float
    acc30: float
    acc60: float
    intensity: float


class RainNowcastResponse(BaseModel):
    segment_id: int
    indices: RainIndicesModel


class RainIngestRequest(BaseModel):
    segment_id: int
    mm_10min: float = Field(..., ge=0.0)


class FieldCheckRequest(BaseModel):
    segment_id: int
    device_hash: str
    lat: float
    lng: float
    photo_url: Optional[str]


class RouteSubscriptionRequest(BaseModel):
    user_id: str
    mode: str
    polyline: str
    quiet_hours: Optional[str] = None
    max_push_per_day: int = Field(3, ge=1)


@app.get("/segments", response_model=List[SegmentResponse])
def list_segments(
    kind: Optional[str] = None,
    state: Optional[str] = None,
    scheduler: Scheduler = Depends(scheduler_dep),
):
    scheduler.enqueue_refresh()
    scheduler.enqueue_release()
    kinds = [SegmentKind(k) for k in kind.split(",") if k] if kind else None
    states = [SegmentState(s) for s in state.split(",") if s] if state else None
    return [SegmentResponse.from_segment(seg) for seg in store.get_segments(kind=kinds, state=states)]


@app.get("/rain/nowcast", response_model=RainNowcastResponse)
def rain_nowcast(segment_id: int):
    if segment_id not in store.segments:
        raise HTTPException(status_code=404, detail="segment not found")
    indices = store.get_rain_indices(segment_id)
    return RainNowcastResponse(segment_id=segment_id, indices=RainIndicesModel(**indices.__dict__))


@app.post("/rain/ingest", response_model=RainNowcastResponse)
def rain_ingest(payload: RainIngestRequest):
    if payload.segment_id not in store.segments:
        raise HTTPException(status_code=404, detail="segment not found")
    indices = ingest_rainfall(payload.segment_id, payload.mm_10min)
    return RainNowcastResponse(segment_id=payload.segment_id, indices=RainIndicesModel(**indices.__dict__))


@app.post("/field-check", response_model=dict)
def submit_field_check(payload: FieldCheckRequest):
    if payload.segment_id not in store.segments:
        raise HTTPException(status_code=404, detail="segment not found")
    confirmations = register_field_check(
        segment_id=payload.segment_id,
        device_hash=payload.device_hash,
        lat=payload.lat,
        lng=payload.lng,
        photo_url=payload.photo_url,
    )
    return {"segment_id": payload.segment_id, "confirmations": confirmations}


@app.post("/routes/subscribe", response_model=dict)
def subscribe_route(payload: RouteSubscriptionRequest):
    route = store.add_route(
        RouteSubscription(
            user_id=payload.user_id,
            mode=payload.mode,
            polyline=payload.polyline,
            quiet_hours=payload.quiet_hours,
            max_push_per_day=payload.max_push_per_day,
        )
    )
    return {"route_id": route.id}


@app.get("/routes", response_model=list)
def list_routes():
    routes = []
    for route in store.list_routes():
        data = asdict(route)
        data["created_at"] = route.created_at.isoformat()
        routes.append(data)
    return routes


@app.get("/reports/weekly", response_model=dict)
def weekly_report(start: Optional[str] = None, end: Optional[str] = None):
    return {
        "start": start,
        "end": end,
        "stats": {
            "alerts_sent": len(store.alerts),
            "avg_risk_score": round(
                sum(segment.risk_score for segment in store.segments.values())
                / max(len(store.segments), 1),
                3,
            ),
            "qr_confirmations": sum(
                len(store.recent_field_checks(segment_id)) for segment_id in store.segments
            ),
        },
    }


@app.get("/tiles/{layer}/{z}/{x}/{y}.png")
def get_tile(layer: str, z: int, x: int, y: int):
    content = render_tile(layer)
    return Response(content=content, media_type="image/png")


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/")
def root():
    return {
        "message": "Landslide Protector API",
        "endpoints": [
            "/segments",
            "/rain/nowcast",
            "/rain/ingest",
            "/field-check",
            "/routes/subscribe",
            "/routes",
        ],
    }
