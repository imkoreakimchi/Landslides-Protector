# Landslide Protector Frontend MVP

React + Vite PWA skeleton that renders Kakao Map overlays backed by the FastAPI sandbox.

## Prerequisites
- Node.js **18.x 또는 20.x LTS** (Vite 5 지원 범위)
- npm **8 이상** (Node 18/20 설치 시 기본 포함)

> Node 22 환경에서 기본 포함되지 않은 **구버전 npm(예: 6.x)** 을 사용할 경우
> `npm WARN npm does not support Node.js v22.x` 경고와 함께 설치가 실패할 수 있습니다.
> `npm install -g npm@latest` 또는 Node 20 LTS 재설치를 통해 npm 10.x 이상으로
> 업데이트한 뒤 진행하세요.

## Setup

1. Install dependencies
   ```bash
   npm install
   ```
2. Copy your Kakao JavaScript API key into `public/index.html` (`YOUR_KAKAO_JS_KEY`).
3. Launch the dev server (backend must run on :8000):
   ```bash
   npm run dev
   ```
   Vite is configured to bind to `0.0.0.0:5173`, so you can also open it from
   phones or other devices on the same network via `http://<your-ip>:5173`.

The app pulls segments, rainfall indices, and raster tiles from `/api/*`
endpoints.
