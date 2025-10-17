"""
Simple HTTP layer over the POC heatmap pipeline.

Usage:
    python3 UberHeatmap/heatmap_server.py --port 8080

Endpoints:
    GET /tiles?layer=demand&zoom=12&window_size=60[&window_start=ISO8601][&refresh=1]
    POST /events   (body: {"events": [...]})

GET returns the latest or requested tile. When `refresh=1` is supplied the
server invalidates any cached payload for that tile before regenerating it.

POST allows clients to push new events (matching the schema used in fixtures),
which updates aggregates and cache state in-memory so subsequent GETs reflect
the new data.

This server is intentionally lightweight and single-process; it demonstrates how
the TileBuilder/HeatmapAPI could be exposed to clients.
"""

from __future__ import annotations

import argparse
import json
import collections
import threading
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

from UberHeatmap.poc import (
    AggregateStore,
    Event,
    GridIndexer,
    HeatmapAPI,
    StreamNormalizer,
    StreamingAggregator,
    TileBuilder,
    generate_sample_events,
    load_events_from_directory,
    parse_timestamp,
)


@dataclass
class HeatmapServiceContext:
    api: HeatmapAPI
    normalizer: StreamNormalizer
    aggregator: StreamingAggregator
    aggregate_store: AggregateStore
    tile_builder: TileBuilder
    latest_windows: Dict[Tuple[str, int, int], datetime]

    def __post_init__(self) -> None:
        self.metrics: collections.Counter[str] = collections.Counter()
        self.lock = threading.Lock()
        self.background_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.auto_config: Optional[Dict[str, float]] = None
        self.last_ingest_at: Optional[datetime] = None

    def process_events(self, events: Sequence[Event]) -> Tuple[Dict[str, int], Dict[Tuple[str, int, int], datetime]]:
        metrics = collections.Counter()
        touched_keys: set[Tuple[str, int, int]] = set()

        with self.lock:
            for event in events:
                metrics["raw"] += 1
                normalized_events = self.normalizer.normalize_event(event)
                for normalized in normalized_events:
                    metrics["normalized"] += 1
                    deltas = self.aggregator.process_event(normalized)
                    for delta in deltas:
                        metrics["deltas"] += 1
                        self.aggregate_store.upsert(delta)
                        self.tile_builder.invalidate(delta.layer, delta.zoom_level, delta.window_size, delta.window_start)
                        metrics["persisted"] += 1
                        key = (delta.layer, delta.zoom_level, delta.window_size)
                        previous = self.latest_windows.get(key)
                        if previous is None or delta.window_start > previous:
                            self.latest_windows[key] = delta.window_start
                        touched_keys.add(key)

            self.metrics.update(metrics)
            if metrics:
                self.last_ingest_at = datetime.utcnow()

        updated_windows = {key: self.latest_windows[key] for key in touched_keys}
        return dict(metrics), updated_windows

    def start_background_ingestion(self, interval_seconds: float, batch_size: int) -> None:
        if self.background_thread and self.background_thread.is_alive():
            return

        self.stop_event.clear()
        self.auto_config = {
            "interval_seconds": interval_seconds,
            "batch_size": batch_size,
        }

        def _ingest_loop() -> None:
            while not self.stop_event.wait(interval_seconds):
                events = generate_sample_events(datetime.utcnow(), count=batch_size)
                self.process_events(events)

        self.background_thread = threading.Thread(target=_ingest_loop, daemon=True)
        self.background_thread.start()

    def stop_background_ingestion(self) -> None:
        if self.background_thread and self.background_thread.is_alive():
            self.stop_event.set()
            self.background_thread.join(timeout=5)
        self.background_thread = None
        self.auto_config = None


class HeatmapRequestHandler(BaseHTTPRequestHandler):
    context: HeatmapServiceContext | None = None

    def do_GET(self) -> None:
        if self.context is None:
            self._send_json({"error": "service not initialised"}, status=500)
            return

        parsed = urlparse(self.path)
        if parsed.path == "/status":
            self._send_json(self._status_payload())
            return

        if parsed.path != "/tiles":
            self._send_json({"error": "not found"}, status=404)
            return

        params = parse_qs(parsed.query)
        try:
            layer = params["layer"][0]
            zoom = int(params.get("zoom", [12])[0])
            window_size = int(params.get("window_size", [60])[0])
        except (KeyError, ValueError, TypeError):
            self._send_json(
                {"error": "layer, zoom, and window_size query parameters are required"},
                status=400,
            )
            return

        window_start_param = params.get("window_start", [None])[0]
        refresh_requested = params.get("refresh", ["0"])[0] not in ("0", "false", "False", "", None)
        key = (layer, zoom, window_size)

        if window_start_param:
            try:
                window_start = datetime.fromisoformat(window_start_param)
            except ValueError:
                self._send_json({"error": "window_start must be ISO8601 datetime"}, status=400)
                return
        else:
            window_start = self.context.latest_windows.get(key)
            if window_start is None:
                self._send_json({"error": f"no data for {key}"}, status=404)
                return

        if refresh_requested:
            self.context.tile_builder.invalidate(layer, zoom, window_size, window_start)

        tile = self.context.api.get_tile(layer, zoom, window_size, window_start)
        self._send_json(tile)

    def do_POST(self) -> None:
        if self.context is None:
            self._send_json({"error": "service not initialised"}, status=500)
            return

        parsed = urlparse(self.path)
        if parsed.path != "/events":
            self._send_json({"error": "not found"}, status=404)
            return

        length_header = self.headers.get("Content-Length")
        if not length_header:
            self._send_json({"error": "Content-Length header required"}, status=411)
            return
        try:
            content_length = int(length_header)
        except ValueError:
            self._send_json({"error": "Invalid Content-Length"}, status=400)
            return

        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Body must be valid JSON"}, status=400)
            return

        events_payload = payload.get("events") if isinstance(payload, dict) else payload
        if not isinstance(events_payload, list) or not events_payload:
            self._send_json({"error": "Request must include non-empty 'events' list"}, status=400)
            return

        events: list[Event] = []
        try:
            for item in events_payload:
                events.append(
                    Event(
                        event_id=item["event_id"],
                        event_type=item["event_type"],
                        timestamp=parse_timestamp(item["timestamp"]),
                        latitude=float(item["latitude"]),
                        longitude=float(item["longitude"]),
                        city_id=item["city_id"],
                        metadata=item.get("metadata", {}),
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            self._send_json({"error": f"Invalid event payload: {exc}"}, status=400)
            return

        metrics, updated_windows = self.context.process_events(events)
        response = {
            "processed": metrics,
            "updated_windows": {
                f"{layer}:{zoom}:{window_size}": window_start.isoformat()
                for (layer, zoom, window_size), window_start in updated_windows.items()
            },
        }
        self._send_json(response, status=202)

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - BaseHTTPRequestHandler signature
        # Suppress default logging to keep demo output tidy.
        return

    def _send_json(self, payload: Dict[str, object], status: int = 200) -> None:
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _status_payload(self) -> Dict[str, object]:
        assert self.context is not None
        with self.context.lock:
            latest_windows = {
                f"{layer}:{zoom}:{window_size}": window_start.isoformat()
                for (layer, zoom, window_size), window_start in self.context.latest_windows.items()
            }
            metrics = dict(self.context.metrics)
            background = None
            if self.context.auto_config:
                background = {
                    "interval_seconds": self.context.auto_config["interval_seconds"],
                    "batch_size": int(self.context.auto_config["batch_size"]),
                    "active": bool(self.context.background_thread and self.context.background_thread.is_alive()),
                }
            return {
                "metrics": metrics,
                "latest_windows": latest_windows,
                "last_ingest_at": self.context.last_ingest_at.isoformat() if self.context.last_ingest_at else None,
                "background_ingestion": background,
            }


def build_context(use_fixture: bool = True) -> HeatmapServiceContext:
    aggregate_store = AggregateStore()
    tile_builder = TileBuilder(aggregate_store)
    api = HeatmapAPI(tile_builder)
    normalizer = StreamNormalizer(GridIndexer(), target_zoom_levels=[10, 12])
    aggregator = StreamingAggregator(window_sizes=[60, 300])
    latest_windows: Dict[Tuple[str, int, int], datetime] = {}

    context = HeatmapServiceContext(
        api=api,
        normalizer=normalizer,
        aggregator=aggregator,
        aggregate_store=aggregate_store,
        tile_builder=tile_builder,
        latest_windows=latest_windows,
    )

    data_dir = Path(__file__).with_name("data")
    if use_fixture and data_dir.exists():
        events = load_events_from_directory(data_dir)
        print(f"[heatmap_server] Loaded {len(events)} events from fixture directory {data_dir}")
    else:
        events = generate_sample_events(datetime.utcnow(), count=200)
        print(f"[heatmap_server] Generated {len(events)} synthetic events")

    metrics, _ = context.process_events(events)
    print(
        "[heatmap_server] Bootstrap metrics:",
        f"raw={metrics.get('raw')}, normalized={metrics.get('normalized')}, deltas={metrics.get('deltas')}",
    )

    return context


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the heatmap HTTP server")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind the HTTP server")
    parser.add_argument("--no-fixture", action="store_true", help="Generate synthetic events instead of fixtures")
    parser.add_argument("--auto-ingest", action="store_true", help="Enable background synthetic ingestion")
    parser.add_argument("--ingest-interval", type=float, default=5.0, help="Seconds between auto-ingest batches")
    parser.add_argument("--ingest-batch-size", type=int, default=25, help="Events per auto-ingest batch")
    args = parser.parse_args()

    context = build_context(use_fixture=not args.no_fixture)
    HeatmapRequestHandler.context = context

    if args.auto_ingest:
        context.start_background_ingestion(args.ingest_interval, args.ingest_batch_size)

    server = HTTPServer(("0.0.0.0", args.port), HeatmapRequestHandler)
    print(f"[heatmap_server] Serving heatmap tiles on http://localhost:{args.port}/tiles")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[heatmap_server] Shutting down...")
    finally:
        context.stop_background_ingestion()
        server.server_close()


if __name__ == "__main__":
    main()
