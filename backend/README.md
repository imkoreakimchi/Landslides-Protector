# Landslide Protector Backend MVP

This FastAPI application provides a lightweight simulation of the landslide risk engine.
It exposes endpoints to:

- fetch segment states and risk scores
- ingest synthetic rainfall and derive intensity/accumulation indices
- record QR-based field checks that confirm closures
- subscribe routes for future alerting flows
- return mock raster tiles for hazard, rain and burn mask layers
- generate a stub weekly report summary

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API listens on `http://localhost:8000`. Combine it with the frontend dev server to see the Kakao Map overlays in action.
