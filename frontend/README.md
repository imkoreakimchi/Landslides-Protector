# Landslide Protector Frontend MVP

React + Vite PWA skeleton that renders Kakao Map overlays backed by the FastAPI sandbox.

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

The app pulls segments, rainfall indices, and raster tiles from `/api/*` endpoints.
