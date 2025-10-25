import { useCallback, useEffect, useRef, useState } from "react";
import { Map, Polyline } from "react-kakao-maps-sdk";

const TILE_BASE = "/api/tiles";

interface Segment {
  id: number;
  name: string;
  kind: "road" | "underpass" | "trail" | "walk";
  hazard_grade: number;
  slope: number;
  burn_mask: boolean;
  coords: [number, number][];
  state: "OPEN" | "CAUTION" | "CLOSED_PENDING" | "CLOSED_CONFIRMED";
  risk_score: number;
}

interface RainResponse {
  segment_id: number;
  indices: {
    acc15: number;
    acc30: number;
    acc60: number;
    intensity: number;
  };
}

declare global {
  interface Window {
    kakao: any;
  }
}

const lineStyle = (state: Segment["state"]) => {
  switch (state) {
    case "CLOSED_CONFIRMED":
      return { strokeWeight: 6, strokeColor: "#c62828", strokeOpacity: 0.9 };
    case "CLOSED_PENDING":
      return { strokeWeight: 6, strokeColor: "#ef5350", strokeOpacity: 0.85, strokeStyle: "shortdash" as const };
    case "CAUTION":
      return { strokeWeight: 5, strokeColor: "#fb8c00", strokeOpacity: 0.9 };
    default:
      return { strokeWeight: 4, strokeColor: "#2e7d32", strokeOpacity: 0.9 };
  }
};

function registerTileset(id: string, layer: string) {
  const { kakao } = window;
  const ts = new kakao.maps.Tileset(
    256,
    256,
    (x: number, y: number, z: number) => `${TILE_BASE}/${layer}/${z}/${x}/${y}.png`,
    [],
    false,
    6,
    15
  );
  kakao.maps.Tileset.add(id, ts);
}

const hazardLayers = [
  { id: "HAZARD", layer: "hazard", label: "위험격자" },
  { id: "RAIN", layer: "rain", label: "강우" },
  { id: "BURN", layer: "burn", label: "번스카 마스크" },
];

export default function App() {
  const mapRef = useRef<any>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null);
  const [layers, setLayers] = useState<Record<string, boolean>>({ HAZARD: true, RAIN: false, BURN: true });
  const [rainPreview, setRainPreview] = useState<RainResponse | null>(null);
  const [subscriptionId, setSubscriptionId] = useState<number | null>(null);

  const fetchSegments = useCallback(async () => {
    const response = await fetch("/api/segments");
    if (!response.ok) return;
    const data: Segment[] = await response.json();
    setSegments(data);
    if (selectedSegment) {
      const refreshed = data.find((s) => s.id === selectedSegment.id) || null;
      setSelectedSegment(refreshed);
    }
  }, [selectedSegment]);

  const toggleOverlay = useCallback((id: string, visible: boolean) => {
    const map = mapRef.current;
    if (!map) return;
    const { kakao } = window;
    const mtid = kakao.maps.MapTypeId[id];
    if (visible) {
      map.addOverlayMapTypeId(mtid);
    } else {
      map.removeOverlayMapTypeId(mtid);
    }
  }, []);

  const handleRainIngest = useCallback(
    async (segmentId: number, mm: number) => {
      const res = await fetch("/api/rain/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segment_id: segmentId, mm_10min: mm }),
      });
      if (!res.ok) return;
      const payload: RainResponse = await res.json();
      setRainPreview(payload);
      fetchSegments();
    },
    [fetchSegments]
  );

  const handleFieldCheck = useCallback(
    async (segmentId: number) => {
      await fetch("/api/field-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          segment_id: segmentId,
          device_hash: "demo-device",
          lat: 37.5665,
          lng: 126.978,
          photo_url: null,
        }),
      });
      fetchSegments();
    },
    [fetchSegments]
  );

  const handleRouteSubscribe = useCallback(async () => {
    const res = await fetch("/api/routes/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: "demo-user",
        mode: "trail",
        polyline: "126.978,37.566;126.985,37.57",
        quiet_hours: "22:00-07:00",
        max_push_per_day: 2,
      }),
    });
    if (!res.ok) return;
    const payload = await res.json();
    setSubscriptionId(payload.route_id);
  }, []);

  useEffect(() => {
    fetchSegments();
  }, [fetchSegments]);

  return (
    <div className="layout">
      <div className="panel">
        <h1>산사태 위험 MVP</h1>
        <section>
          <h2>레이어</h2>
          {hazardLayers.map((layer) => (
            <label key={layer.id}>
              <input
                type="checkbox"
                checked={layers[layer.id]}
                onChange={(event) => {
                  const checked = event.target.checked;
                  setLayers((current) => ({ ...current, [layer.id]: checked }));
                  toggleOverlay(layer.id, checked);
                }}
              />
              {layer.label}
            </label>
          ))}
        </section>
        <section>
          <h2>세그먼트</h2>
          <ul className="segments">
            {segments.map((segment) => (
              <li key={segment.id} onClick={() => setSelectedSegment(segment)}>
                <span>{segment.name}</span>
                <span className={`state state-${segment.state.toLowerCase()}`}>{segment.state}</span>
                <small>risk {segment.risk_score.toFixed(2)}</small>
              </li>
            ))}
          </ul>
        </section>
        {selectedSegment && (
          <section>
            <h2>현장 제어</h2>
            <p>
              <strong>{selectedSegment.name}</strong>
            </p>
            <button onClick={() => handleRainIngest(selectedSegment.id, 3)}>강우 +3mm/10분</button>
            <button onClick={() => handleRainIngest(selectedSegment.id, 0)}>강우 0mm(해제)</button>
            <button onClick={() => handleFieldCheck(selectedSegment.id)}>QR 현장확정</button>
          </section>
        )}
        {rainPreview && (
          <section>
            <h2>강우 지표</h2>
            <p>세그먼트 #{rainPreview.segment_id}</p>
            <p>
              acc15: {rainPreview.indices.acc15.toFixed(1)} / acc30: {rainPreview.indices.acc30.toFixed(1)} / acc60: {rainPreview.indices.acc60.toFixed(1)}
            </p>
            <p>intensity: {rainPreview.indices.intensity.toFixed(1)} mm/h</p>
          </section>
        )}
        <section>
          <h2>경로 구독</h2>
          <button onClick={handleRouteSubscribe}>샘플 경로 등록</button>
          {subscriptionId && <p className="hint">route #{subscriptionId} 구독 완료</p>}
        </section>
      </div>
      <div className="map">
        <Map
          center={{ lat: 37.5665, lng: 126.978 }}
          level={7}
          style={{ width: "100%", height: "100%" }}
          onCreate={(map) => {
            mapRef.current = map;
            window.kakao.maps.load(() => {
              hazardLayers.forEach(({ id, layer }) => registerTileset(id, layer));
              setTimeout(() => {
                Object.entries(layers).forEach(([id, active]) => toggleOverlay(id, active));
              }, 0);
              window.kakao.maps.event.addListener(map, "idle", () => {
                fetchSegments();
              });
            });
          }}
        >
          {segments.map((segment) => (
            <Polyline
              key={segment.id}
              path={segment.coords.map(([lng, lat]) => ({ lat, lng }))}
              {...lineStyle(segment.state)}
            />
          ))}
        </Map>
      </div>
    </div>
  );
}
