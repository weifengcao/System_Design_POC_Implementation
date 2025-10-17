import unittest
from datetime import datetime, timedelta

from UberHeatmap.poc import (
    AggregateDelta,
    AggregateStore,
    GridIndexer,
    NormalizedEvent,
    StreamingAggregator,
    TileBuilder,
)


class StreamingAggregatorTests(unittest.TestCase):
    def test_counts_accumulate_per_window(self) -> None:
        aggregator = StreamingAggregator(window_sizes=[60])
        ts = datetime(2025, 10, 17, 21, 30, 5)

        events = [
            NormalizedEvent(
                event_id=f"evt_{idx}",
                event_type="ride_request",
                timestamp=ts + timedelta(seconds=idx * 10),
                city_id="san_francisco",
                cell_id="cell_z12_0_0",
                zoom_level=12,
                layer="demand",
            )
            for idx in range(3)
        ]

        deltas = []
        for event in events:
            deltas.extend(aggregator.process_event(event))

        self.assertEqual(len(deltas), 3)
        self.assertTrue(all(delta.count == idx + 1 for idx, delta in enumerate(deltas)))
        window_start = deltas[-1].window_start
        self.assertEqual(window_start.second, 0)


class TileBuilderTests(unittest.TestCase):
    def test_invalidate_clears_cached_tile(self) -> None:
        store = AggregateStore()
        builder = TileBuilder(store)
        window_start = datetime(2025, 10, 17, 21, 30, 0)
        delta = AggregateDelta(
            layer="demand",
            zoom_level=12,
            cell_id="cell_z12_1_1",
            window_size=60,
            window_start=window_start,
            count=2,
        )
        store.upsert(delta)

        tile_a = builder.build_tile("demand", 12, 60, window_start)
        tile_b = builder.build_tile("demand", 12, 60, window_start)
        self.assertIs(tile_a, tile_b, "Tile should be served from cache")

        builder.invalidate("demand", 12, 60, window_start)
        self.assertEqual(len(builder.tile_cache), 0)

        # Update store and rebuild tile to ensure cache repopulates.
        updated_delta = AggregateDelta(
            layer="demand",
            zoom_level=12,
            cell_id="cell_z12_1_1",
            window_size=60,
            window_start=window_start,
            count=3,
        )
        store.upsert(updated_delta)
        tile_c = builder.build_tile("demand", 12, 60, window_start)
        self.assertEqual(tile_c["cells"][0]["count"], 3)
        self.assertEqual(len(builder.tile_cache), 1)


if __name__ == "__main__":
    unittest.main()
