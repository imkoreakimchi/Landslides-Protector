# Landslides Protector

## 목적 및 범위
- **목적**: 카카오맵 기반 모바일 PWA에서 산사태 위험을 실시간으로 시각화하고, 우회 동선을 안내하며, QR 현장 검증과 푸시 알림을 통합합니다.
- **핵심 기능**: 위험 격자 오버레이, 산불피해지 1차 마스킹, 초단기 강우 지표(누적/강도) 산출, 위험등급 기반 상태 전환(Open/주의/통제), QR 기반 현장 확정, 무강우 60분 자동 해제, 경로 구독 알림(대중교통/자차/등산/도보), 주간 리포트 자동화.

## 전체 아키텍처
```
[Client (PWA, React)] --HTTPS--> [API Gateway (Spring Boot)] --gRPC/REST--> [Geo Engine (Python/GeoPandas)]
      |                                         |                              |
      |                                         |                              +--> [Raster/Vector Tile Server]
      |                                         |
      |                                         +--> [Scheduler (Airflow/Quartz)]
      |
      +-- Web Push(SW/FCM) <-- [Alert Service] <-- [Risk Engine] <-- [Data Lake/Warehouse]
                                                                          |
                [PostgreSQL + PostGIS + TimescaleDB] <---------------------+
                                                                          |
                                [Ingestion Workers: KMA, IMERG, KFS, KNPS, OSM]
```

### 주요 구성요소
- **프런트엔드**: React PWA, `react-kakao-maps-sdk`, Service Worker(웹푸시/오프라인 캐시).
- **API Gateway**: Spring Boot, 인증/권한, 속도제한, 외부 API 키 주입, 서명된 타일 URL 발급.
- **Geo Engine**: FastAPI + GeoPandas/PostGIS, 공간 연산(세그먼트 분할·교차·버퍼), 강우 지표 집계, 위험 점수 산정.
- **Tile Server**: 위험 격자·강우·번스카 라스터 XYZ, 세그먼트 MVT.
- **Scheduler**: Airflow/Quartz, 주기적 ETL·타일 리빌드.
- **Alert Service**: 푸시/쿨다운/조용시간 제어, 경로 구독자 알림.
- **Reporting**: 주간 PDF 생성(Puppeteer/WeasyPrint) 및 배포.

## MVP 샌드박스(코드 제공)

실제 구축에 앞서 핵심 플로우를 빠르게 검증할 수 있도록 `backend/`와 `frontend/` 디렉터리에 최소 실행 가능한 샘플을 추가했습니다.

| 구성 | 설명 |
| --- | --- |
| FastAPI 백엔드 (`backend/`) | 세그먼트 상태·위험 점수 계산, 강우 지표 산출, QR 현장확인, 경로 구독, 주간 리포트 요약, 타일(위험/강우/번스카) 더미 PNG 제공 |
| React PWA 프런트 (`frontend/`) | Kakao Map + `react-kakao-maps-sdk`로 지도 표시, 타일 오버레이 토글, 세그먼트 상태 시각화, 강우/QR 테스트 트리거 |

### 실행 순서

1. **백엔드**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
2. **프런트엔드**
   ```bash
   cd frontend
   npm install
   # Kakao JS 키를 public/index.html에 입력
   npm run dev
   ```
3. 브라우저에서 `http://localhost:5173` 접속 후 타일 오버레이/세그먼트 상태/강우 지표/QR 현장확정을 시험합니다.

> ⚠️ 현재 데이터는 인메모리 더미이며, 실제 API·DB·타일서버로 교체해야 합니다. 구조만 먼저 확인하세요.

## 데이터 소스 및 동기화 주기
| 데이터 | 내용 | 주기 |
| --- | --- | --- |
| KMA 초단기 실황/예보 | 5km 격자, 10분 간격. 15/30/60분 누적 및 순간강도 파생. | 10분 |
| 산사태 위험지도 | 10m, 1~5등급. 파일 또는 WMS. | 12시간 |
| 산불 피해지(번스카) | 산림청 폴리곤, NASA FIRMS 보조. | 변경 시 |
| 국립공원 탐방로/입산통제 | 탐방로 네트워크, 통제현황. | 1~24시간 |
| 도로/지하차도/등산로 세그먼트 | OSM/국가공간정보 기반. | 초기 구축 + 증분 |

## 세그먼트 구축 파이프라인
1. **네트워크 수집**: 도로·지하차도·등산로·생활로 데이터 확보.
2. **세그먼트화**: 교차점 기준 분할, `underpass=true` 태깅.
3. **속성추가**: 고도, 경사, 위험/취약지역 포함 여부, 번스카 교차 여부.
4. **타일화**: 야간에 MVT(세그먼트)와 라스터(위험/강우) 빌드.

## 강우 파생지표 계산
- **누적강우(R_acc)**: 15/30/60분 이동합, 결측 시 보간.
- **순간강도(R_int)**: 최근 10분 강우량 × 6(mm/h) + 변화율.
- **레이더 음영 보완**: IMERG Early/Final 데이터로 가중 보정.

## 위험도 산정 및 상태머신
- `risk = w1*H + w2*norm(R_acc) + w3*norm(R_int) + w4*B + w5*T + w6*U`
  - H: 위험지도 등급, B: 번스카, T: 지형 보정, U: 시설 타입 보정.
- 임계치 예시
  - `OPEN`: risk < τ1
  - `주의`: τ1 ≤ risk < τ2
  - `통제(잠정)`: risk ≥ τ2 → QR 일치 N건(≥2)로 `통제(확정)` 승격
  - **해제**: 무강우 60분 지속 시 단계적 하향(히스테리시스 적용).

## API 설계 개요
- **Tiles**
  - `GET /tiles/hazard/{z}/{x}/{y}.png`
  - `GET /tiles/rain/{z}/{x}/{y}.png`
  - `GET /tiles/mask_burn/{z}/{x}/{y}.png`
  - `GET /tiles/segments/{z}/{x}/{y}.mvt`
- **세그먼트/상태**
  - `GET /segments?bbox=...&type=...`
  - `GET /segments/{id}/history`
  - `POST /segments/{id}/override`
- **강우/지표**
  - `GET /rain/nowcast?lat=..&lng=..`
  - `GET /rain/accum?lat=..&lng=..&window=15|30|60`
- **QR 현장확인**
  - `POST /field-check`
  - `GET /field-checks?segment_id=..`
- **경로 구독/알림**
  - `POST /routes/subscribe`
  - `POST /alerts/test`, `GET /alerts`
  - `POST /webpush/subscribe`
- **리포트**
  - `GET /reports/weekly?start=..&end=..`

## 프런트엔드(PWA)
- React + Vite/Next 기반, `react-kakao-maps-sdk`로 지도 렌더링.
- Kakao Tileset 커스텀 오버레이(위험/강우/번스카) + 세그먼트 Polyline/MVT 스타일링.
- QR 스캔(getUserMedia + jsQR/zxing), Web Push(FCM/VAPID), IndexedDB 캐시.

## 서버 구성요소
- **Gateway**: Spring Boot + Spring Security, Rate Limit, 외부 API 프록시.
- **Geo Engine**: FastAPI, GeoPandas, Rasterio, GDAL, PostGIS 연동.
- **Tile Server**: GeoServer 또는 Tileserver-GL, Tippecanoe/Mapnik 파이프라인.
- **Scheduler**: Airflow/Quartz, Celery/Beat 대안.
- **Queue/Push**: Redis Streams, RabbitMQ 또는 Kafka.
- **스토리지**: PostgreSQL + PostGIS + TimescaleDB, S3 호환 객체 스토리지, 이미지/타일 보관.

## 데이터베이스 스키마 요약
```sql
CREATE TABLE hazard_grid (
  id bigserial PRIMARY KEY,
  cell geometry(POLYGON, 4326) NOT NULL,
  grade smallint CHECK (grade BETWEEN 1 AND 5),
  updated_at timestamptz
);

CREATE TABLE rain_cell (
  id bigserial PRIMARY KEY,
  grid_id bigint REFERENCES hazard_grid(id),
  t timestamptz,
  mm numeric(5,2),
  idx_acc15 numeric,
  idx_acc30 numeric,
  idx_acc60 numeric,
  idx_intensity numeric
);

CREATE TABLE segment (
  id bigserial PRIMARY KEY,
  geom geometry(LINESTRING, 4326) NOT NULL,
  kind text CHECK (kind IN ('road','underpass','trail','walk')),
  slope numeric(4,2),
  hazard_grade smallint,
  in_burn_mask boolean DEFAULT false
);

CREATE TABLE segment_state (
  segment_id bigint REFERENCES segment(id),
  t timestamptz,
  state text CHECK (state IN ('OPEN','CAUTION','CLOSED_PENDING','CLOSED_CONFIRMED')),
  risk_score numeric(5,3),
  reason jsonb,
  PRIMARY KEY(segment_id, t)
);

CREATE TABLE field_check (
  id bigserial PRIMARY KEY,
  segment_id bigint REFERENCES segment(id),
  t timestamptz,
  lat numeric(9,6),
  lng numeric(9,6),
  photo_url text,
  device_hash text
);

CREATE TABLE user_route (
  id bigserial PRIMARY KEY,
  user_id uuid,
  mode text CHECK (mode IN ('transit','car','trail','walk')),
  polyline text,
  quiet_hours tstzrange,
  max_push_per_day int DEFAULT 3
);

CREATE TABLE alert_log (
  id bigserial PRIMARY KEY,
  user_id uuid,
  route_id bigint REFERENCES user_route(id),
  segment_id bigint,
  t timestamptz,
  state_from text,
  state_to text,
  sent boolean,
  push_id text
);
```

## 상태머신 의사코드
```pseudo
for each segment s:
  r = sample_rain_indices(s)
  h = s.hazard_grade
  b = s.in_burn_mask
  u = type_weight(s.kind)
  t = terrain_weight(s.slope)
  score = w1*h + w2*norm(r.acc30) + w3*norm(r.intensity) + w4*b + w5*t + w6*u

  next = case
    when score >= τ2 then CLOSED_PENDING
    when score >= τ1 then CAUTION
    else OPEN
  end

  if next == CLOSED_PENDING and qr_confirmations(s, last=90min) >= N:
      next = CLOSED_CONFIRMED

  if rainfall_zero_for(s, 60min):
      demote_state(s)
```

## 운영 스케줄
- 강우 ETL: 10분 주기 수집 → 15/30/60분 집계 및 지표 업데이트.
- 위험/취약 동기화: 00:30, 12:30 등 하루 2회.
- 타일 리빌드: 02:00 야간 증분 빌드.
- 알림 제어: 조용시간(예: 22:00~07:00), 동일 이벤트 쿨다운(≥90분), 일일 최대 발송 횟수.

## 테스트 및 모니터링
1. 시범 구간 30곳 대상 더미 구독자 100명 구성.
2. 강우 시나리오 시뮬레이션 및 실측 비교.
3. KPI: 경보→우회 클릭률, 경보→통제 확정 리드타임, QR 일치율, 실제 진입 감소율.
4. 로그/메트릭: Prometheus/Grafana, 알림 성공률, 타일 생성 지연, API 응답 시간.

## 구현 체크리스트
- [ ] Kakao Maps 키 등록 및 PWA 기본 세팅(Service Worker, VAPID 키).
- [ ] PostGIS/TimescaleDB 설치 및 공간 인덱스 구성.
- [ ] 위험지도/번스카/탐방로/도로 데이터 적재 및 세그먼트화.
- [ ] KMA 수집기/집계기, IMERG 보조 샘플러 구현.
- [ ] 위험도 엔진, 상태머신, 알림 엔진 구축.
- [ ] 타일 서버 설정(라스터 XYZ + MVT) 및 카카오맵 커스텀 오버레이 연동.
- [ ] QR 업로드/검증 플로우 및 관리자 UI 구현.
- [ ] 우회 경로 딥링크(대중교통/자차/등산/도보) 연계.
- [ ] 주간 PDF 리포트 자동화 및 대시보드 공유.
- [ ] 부하/장애/품질 테스트 및 롤백 플랜.
