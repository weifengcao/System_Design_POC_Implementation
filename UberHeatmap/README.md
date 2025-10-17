# Uber Heatmap POC

## Overview
`poc.py` is a self-contained Python script that simulates the Uber demand heatmap pipeline:

- Loads fixture-driven rider and driver events (with a synthetic fallback).
- Normalizes events into pseudo S2 cells for multiple zoom levels.
- Streams events through asynchronous queues to mimic bursty ingestion.
- Aggregates demand/supply counts across tumbling windows.
- Materializes tile payloads that a lightweight API can serve.

## Run the Demo
```bash
python3 UberHeatmap/poc.py
```

The script prints pipeline metrics and a sample tile payload so you can inspect the output quickly.

## Run Tests
```bash
python3 -m unittest UberHeatmap/test_poc.py
# Requires pytest to be installed: `python3 -m pip install pytest`
python3 -m pytest UberHeatmap/test_benchmark.py -s
```

## Run the HTTP Server
```bash
python3 UberHeatmap/heatmap_server.py --port 8080
# Then request a tile:
curl "http://localhost:8080/tiles?layer=demand&zoom=12&window_size=60"
# Invalidate cache and rebuild on demand:
curl "http://localhost:8080/tiles?layer=demand&zoom=12&window_size=60&refresh=1"

# Inspect service health and aggregated metrics:
curl "http://localhost:8080/status"

# Push new events (must include event_id/event_type/timestamp/lat/lon/city_id):
curl -X POST http://localhost:8080/events \
  -H "Content-Type: application/json" \
  -d '{"events": [{"event_id":"evt_cli_1","event_type":"ride_request","timestamp":"2025-10-17T22:45:00Z","latitude":37.775,"longitude":-122.419,"city_id":"san_francisco","metadata":{"source":"cli"}}]}'

# Run with background synthetic ingestion (5s interval, 25 events per batch by default):
python3 UberHeatmap/heatmap_server.py --auto-ingest --ingest-interval 3 --ingest-batch-size 10
```

## Containerize and Run
```bash
docker build -f UberHeatmap/Dockerfile -t uber-heatmap .
docker run --rm -p 8080:8080 uber-heatmap
```
