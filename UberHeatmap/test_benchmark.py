import asyncio
import time
from datetime import datetime

import pytest

from UberHeatmap.poc import (
    AggregateStore,
    GridIndexer,
    StreamNormalizer,
    StreamingAggregator,
    TileBuilder,
    generate_sample_events,
    run_async_pipeline,
)


@pytest.mark.performance
def test_pipeline_throughput() -> None:
    event_count = 500
    events = generate_sample_events(datetime.utcnow(), count=event_count)

    normalizer = StreamNormalizer(GridIndexer(), target_zoom_levels=[10, 12])
    aggregator = StreamingAggregator(window_sizes=[60, 300])
    aggregate_store = AggregateStore()
    tile_builder = TileBuilder(aggregate_store)

    start = time.perf_counter()
    metrics, latest = asyncio.run(
        run_async_pipeline(events, normalizer, aggregator, aggregate_store, tile_builder)
    )
    elapsed = time.perf_counter() - start

    throughput = metrics.get("raw", 0) / elapsed if elapsed > 0 else float("inf")

    # Validate counts to ensure the pipeline processed every event.
    assert metrics.get("raw") == event_count
    assert metrics.get("persisted") == metrics.get("deltas")
    assert latest, "Latest windows should not be empty"

    # Emits a helpful note when running `pytest -s`.
    print(f"\nProcessed {event_count} events in {elapsed:.4f}s (~{throughput:.1f} events/s)")
