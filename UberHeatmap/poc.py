"""
Proof-of-concept implementation for the Uber Demand Heatmap design.

This script simulates the end-to-end pipeline described in design.md:
    1. Ingest geo-tagged rider/driver events.
    2. Normalize events (dedupe, map to geo cells, sanitize).
    3. Aggregate counts per grid cell and time window.
    4. Materialize tiles and cache them for a lightweight API.

The goal is to demonstrate core behaviors without external systems like Kafka,
Flink, Cassandra, or Redis. Everything runs in-memory with deterministic
components so the demo can be executed locally.
"""

from __future__ import annotations

import asyncio
import collections
import dataclasses
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Event:
    """Raw event emitted by upstream publishers."""

    event_id: str
    event_type: str  # e.g., "ride_request", "driver_ping"
    timestamp: datetime
    latitude: float
    longitude: float
    city_id: str
    metadata: Dict[str, str]


@dataclasses.dataclass(frozen=True)
class NormalizedEvent:
    """Event after map matching, dedupe, and cell assignment."""

    event_id: str
    event_type: str
    timestamp: datetime
    city_id: str
    cell_id: str  # simplified cell representation (pseudo S2)
    zoom_level: int
    layer: str  # "demand" or "supply" etc.


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


class GridIndexer:
    """
    Simplified S2-like geospatial indexer.

    Produces deterministic tile identifiers by snapping lat/lon to a grid that
    varies by zoom level. In reality we would use Uber's S2 bindings, but this
    approximation keeps the POC self-contained.
    """

    def __init__(self, base_cell_size_degrees: float = 0.05) -> None:
        self.base_cell_size_degrees = base_cell_size_degrees

    def cell_for(self, latitude: float, longitude: float, zoom: int) -> str:
        # Clamp lat/lon to feasible ranges (simulate map match cleanup).
        lat = max(min(latitude, 90.0), -90.0)
        lon = max(min(longitude, 180.0), -180.0)

        # Increase resolution as zoom grows (roughly doubles per zoom).
        scale = 2 ** max(zoom - 8, 0)
        cell_size = self.base_cell_size_degrees / max(scale, 1)

        lat_bucket = math.floor(lat / cell_size)
        lon_bucket = math.floor(lon / cell_size)
        return f"cell_z{zoom}_{lat_bucket}_{lon_bucket}"


class Deduper:
    """Maintains a short-lived cache of event IDs to eliminate duplicates."""

    def __init__(self) -> None:
        self._seen: Dict[str, datetime] = {}

    def is_duplicate(self, event: Event) -> bool:
        if event.event_id in self._seen:
            return True
        self._seen[event.event_id] = event.timestamp
        self._evict_old_entries(event.timestamp)
        return False

    def _evict_old_entries(self, now: datetime, retention: timedelta = timedelta(minutes=15)) -> None:
        threshold = now - retention
        stale_ids = [event_id for event_id, ts in self._seen.items() if ts < threshold]
        for event_id in stale_ids:
            del self._seen[event_id]


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


class EventIngestor:
    """Simulated ingestion layer that yields raw events."""

    def __init__(self, events: Sequence[Event], sort_events: bool = False) -> None:
        self.events = list(events)
        if sort_events:
            self.events.sort(key=lambda e: e.timestamp)

    def read_events(self) -> Iterable[Event]:
        for event in self.events:
            yield event


class StreamNormalizer:
    """
    Mimics streaming normalization (dedupe + map matching).

    Converts raw events into NormalizedEvent objects at multiple zoom levels to
    align with the downstream aggregator requirements.
    """

    def __init__(self, grid_indexer: GridIndexer, target_zoom_levels: Sequence[int]):
        self.grid_indexer = grid_indexer
        self.target_zoom_levels = list(target_zoom_levels)
        self.deduper = Deduper()

    def normalize(self, events: Iterable[Event]) -> Iterable[NormalizedEvent]:
        for event in events:
            yield from self.normalize_event(event)

    def normalize_event(self, event: Event) -> Iterable[NormalizedEvent]:
        if self.deduper.is_duplicate(event):
            return []

        normalized = []
        for zoom in self.target_zoom_levels:
            cell_id = self.grid_indexer.cell_for(event.latitude, event.longitude, zoom)
            layer = "demand" if event.event_type == "ride_request" else "supply"
            normalized.append(
                NormalizedEvent(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    timestamp=event.timestamp,
                    city_id=event.city_id,
                    cell_id=cell_id,
                    zoom_level=zoom,
                    layer=layer,
                )
            )
        return normalized


class StreamingAggregator:
    """
    Aggregates normalized events into tumbling time windows per cell.

    Instead of running on a distributed engine, this POC keeps state in-memory.
    """

    def __init__(self, window_sizes: Sequence[int]):
        self.window_sizes = list(window_sizes)  # seconds
        # Nested dict keyed by (layer, zoom, cell, window_size, window_start)
        self.state: Dict[Tuple[str, int, str, int, datetime], int] = collections.defaultdict(int)

    def ingest(self, events: Iterable[NormalizedEvent]) -> Iterable["AggregateDelta"]:
        for event in events:
            yield from self.process_event(event)

    def process_event(self, event: NormalizedEvent) -> List["AggregateDelta"]:
        deltas: List[AggregateDelta] = []
        for window_size in self.window_sizes:
            window_start = self._window_floor(event.timestamp, window_size)
            key = (event.layer, event.zoom_level, event.cell_id, window_size, window_start)
            self.state[key] += 1
            deltas.append(
                AggregateDelta(
                    layer=event.layer,
                    zoom_level=event.zoom_level,
                    cell_id=event.cell_id,
                    window_size=window_size,
                    window_start=window_start,
                    count=self.state[key],
                )
            )
        return deltas

    @staticmethod
    def _window_floor(timestamp: datetime, window_size: int) -> datetime:
        epoch_seconds = int(timestamp.timestamp())
        floored = epoch_seconds - (epoch_seconds % window_size)
        return datetime.fromtimestamp(floored)


@dataclasses.dataclass(frozen=True)
class AggregateDelta:
    """Represents an updated aggregate for a cell/window combination."""

    layer: str
    zoom_level: int
    cell_id: str
    window_size: int
    window_start: datetime
    count: int


class AggregateStore:
    """In-memory backing store mimicking Cassandra/DynamoDB."""

    def __init__(self) -> None:
        self._store: Dict[Tuple[str, int, str, int, datetime], AggregateDelta] = {}

    def upsert(self, delta: AggregateDelta) -> None:
        key = (delta.layer, delta.zoom_level, delta.cell_id, delta.window_size, delta.window_start)
        self._store[key] = delta

    def get(self, layer: str, zoom: int, cell_id: str, window_size: int, window_start: datetime) -> AggregateDelta | None:
        return self._store.get((layer, zoom, cell_id, window_size, window_start))

    def scan_tiles(self, layer: str, zoom: int, window_size: int, window_start: datetime) -> List[AggregateDelta]:
        result = []
        for (key_layer, key_zoom, key_cell, key_window_size, key_window_start), delta in self._store.items():
            if (
                key_layer == layer
                and key_zoom == zoom
                and key_window_size == window_size
                and key_window_start == window_start
            ):
                result.append(delta)
        return result


class TileBuilder:
    """
    Materializes tile payloads from aggregate deltas.

    Tiles are stored as JSON-ready dicts so they can be exposed via a REST-like API.
    """

    def __init__(self, aggregate_store: AggregateStore):
        self.aggregate_store = aggregate_store
        self.tile_cache: Dict[Tuple[str, int, int, datetime], Dict[str, object]] = {}

    def build_tile(
        self,
        layer: str,
        zoom: int,
        window_size: int,
        window_start: datetime,
    ) -> Dict[str, object]:
        key = (layer, zoom, window_size, window_start)
        if key in self.tile_cache:
            return self.tile_cache[key]

        aggregates = self.aggregate_store.scan_tiles(layer, zoom, window_size, window_start)
        cells = [{  # Each cell corresponds to an aggregate delta
            "cell_id": delta.cell_id,
            "count": delta.count,
        } for delta in aggregates]

        tile = {
            "layer": layer,
            "zoom": zoom,
            "window_size_seconds": window_size,
            "window_start": window_start.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "cells": cells,
        }
        self.tile_cache[key] = tile
        return tile

    def invalidate(self, layer: str, zoom: int, window_size: int, window_start: datetime) -> None:
        key = (layer, zoom, window_size, window_start)
        self.tile_cache.pop(key, None)


class HeatmapAPI:
    """
    Lightweight façade over the tile builder with an in-process cache.
    """

    def __init__(self, tile_builder: TileBuilder):
        self.tile_builder = tile_builder

    def get_tile(
        self,
        layer: str,
        zoom: int,
        window_size: int,
        window_start: datetime,
    ) -> Dict[str, object]:
        return self.tile_builder.build_tile(layer, zoom, window_size, window_start)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def load_events_from_fixture_file(path: Path) -> List[Event]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    events: List[Event] = []
    for item in payload:
        events.append(
            Event(
                event_id=item["event_id"],
                event_type=item["event_type"],
                timestamp=parse_timestamp(item["timestamp"]),
                latitude=item["latitude"],
                longitude=item["longitude"],
                city_id=item["city_id"],
                metadata=item.get("metadata", {}),
            )
        )
    return events


def load_events_from_directory(directory: Path) -> List[Event]:
    events: List[Event] = []
    for path in sorted(directory.glob("*.json")):
        events.extend(load_events_from_fixture_file(path))
    return events


def generate_sample_events(now: datetime, city_id: str = "san_francisco", count: int = 100) -> List[Event]:
    """
    Fabricate events around San Francisco coordinates to demonstrate the pipeline.
    """
    events: List[Event] = []
    base_lat, base_lon = 37.7749, -122.4194
    for idx in range(count):
        event_type = random.choice(["ride_request", "driver_ping"])
        jitter_lat = random.uniform(-0.02, 0.02)
        jitter_lon = random.uniform(-0.02, 0.02)
        timestamp = now + timedelta(seconds=random.randint(-120, 0))
        events.append(
            Event(
                event_id=f"evt_{idx}",
                event_type=event_type,
                timestamp=timestamp,
                latitude=base_lat + jitter_lat,
                longitude=base_lon + jitter_lon,
                city_id=city_id,
                metadata={"source": "simulation"},
            )
        )
    return sorted(events, key=lambda e: e.timestamp)


# ---------------------------------------------------------------------------
# Async pipeline execution
# ---------------------------------------------------------------------------


async def produce_events(events: Sequence[Event], queue: asyncio.Queue, metrics: Dict[str, int]) -> None:
    for event in events:
        await queue.put(event)
        metrics["raw"] += 1
    await queue.put(None)  # Sentinel to close the stream.


async def normalize_events(
    normalizer: StreamNormalizer,
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue,
    metrics: Dict[str, int],
) -> None:
    while True:
        event = await input_queue.get()
        if event is None:
            await output_queue.put(None)
            break
        for normalized in normalizer.normalize_event(event):
            await output_queue.put(normalized)
            metrics["normalized"] += 1


async def aggregate_events(
    aggregator: StreamingAggregator,
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue,
    metrics: Dict[str, int],
) -> None:
    while True:
        normalized = await input_queue.get()
        if normalized is None:
            await output_queue.put(None)
            break
        for delta in aggregator.process_event(normalized):
            await output_queue.put(delta)
            metrics["deltas"] += 1


async def persist_deltas(
    aggregate_store: AggregateStore,
    tile_builder: TileBuilder,
    input_queue: asyncio.Queue,
    metrics: Dict[str, int],
    latest_windows: Dict[Tuple[str, int, int], datetime],
) -> None:
    while True:
        delta = await input_queue.get()
        if delta is None:
            break
        aggregate_store.upsert(delta)
        tile_builder.invalidate(delta.layer, delta.zoom_level, delta.window_size, delta.window_start)
        metrics["persisted"] += 1
        key = (delta.layer, delta.zoom_level, delta.window_size)
        previous = latest_windows.get(key)
        if previous is None or delta.window_start > previous:
            latest_windows[key] = delta.window_start


async def run_async_pipeline(
    events: Sequence[Event],
    normalizer: StreamNormalizer,
    aggregator: StreamingAggregator,
    aggregate_store: AggregateStore,
    tile_builder: TileBuilder,
) -> Tuple[Dict[str, int], Dict[Tuple[str, int, int], datetime]]:
    metrics = collections.Counter()  # raw, normalized, deltas, persisted
    latest_windows: Dict[Tuple[str, int, int], datetime] = {}

    ingest_queue: asyncio.Queue = asyncio.Queue()
    normalized_queue: asyncio.Queue = asyncio.Queue()
    delta_queue: asyncio.Queue = asyncio.Queue()

    tasks = [
        asyncio.create_task(produce_events(events, ingest_queue, metrics)),
        asyncio.create_task(normalize_events(normalizer, ingest_queue, normalized_queue, metrics)),
        asyncio.create_task(aggregate_events(aggregator, normalized_queue, delta_queue, metrics)),
        asyncio.create_task(persist_deltas(aggregate_store, tile_builder, delta_queue, metrics, latest_windows)),
    ]

    await asyncio.gather(*tasks)
    return dict(metrics), latest_windows


# ---------------------------------------------------------------------------
# Demo driver
# ---------------------------------------------------------------------------


def run_demo() -> None:
    print("🚕 Running Uber Demand Heatmap POC...\n")

    data_dir = Path(__file__).with_name("data")
    if data_dir.exists():
        events = load_events_from_directory(data_dir)
        fixture_files = ", ".join(sorted(p.name for p in data_dir.glob("*.json")))
        print(f"Loaded {len(events)} events from fixtures: {fixture_files or 'none found'}")
    else:
        now = datetime.utcnow()
        events = generate_sample_events(now)
        print(f"Fixture not found; generated {len(events)} synthetic events.")

    ingestor = EventIngestor(events)
    normalizer = StreamNormalizer(GridIndexer(), target_zoom_levels=[10, 12])
    aggregator = StreamingAggregator(window_sizes=[60, 300])
    aggregate_store = AggregateStore()
    tile_builder = TileBuilder(aggregate_store)
    api = HeatmapAPI(tile_builder)

    metrics, latest_windows = asyncio.run(
        run_async_pipeline(list(ingestor.read_events()), normalizer, aggregator, aggregate_store, tile_builder)
    )

    print(f"Ingested {metrics.get('raw', 0)} raw events")
    print(f"Normalized into {metrics.get('normalized', 0)} cell events")
    print(f"Produced {metrics.get('deltas', 0)} aggregate updates")
    print(f"Persisted {metrics.get('persisted', 0)} aggregates\n")

    if not latest_windows:
        print("No aggregates generated; exiting.")
        return

    sample_key = ("demand", 12, 60)
    if sample_key not in latest_windows:
        sample_key = next(iter(latest_windows.keys()))

    layer, zoom, window_size = sample_key
    latest_window_start = latest_windows[sample_key]
    sample_tile = api.get_tile(layer=layer, zoom=zoom, window_size=window_size, window_start=latest_window_start)

    print(f"Sample tile (layer={layer}, zoom={zoom}, window={window_size}s):")
    print(json.dumps(sample_tile, indent=2))

    print("\nDone.")


if __name__ == "__main__":
    random.seed(42)
    run_demo()
