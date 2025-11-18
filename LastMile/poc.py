"""
Simple proof-of-concept for the LastMile design.

The script wires lightweight "agents" together to simulate a planning cycle:
1. OrderIntakeAgent validates raw orders and enriches them with locations.
2. CapacityAgent exposes available drivers and their vehicles.
3. SignalAgent produces hazard multipliers that emulate traffic/weather.
4. PlannerAgent assigns orders to drivers using a heuristic priority score.
5. RouteOptimizationAgent builds naive routes/ETAs based on distance & hazards.
6. SLAGuardianAgent checks whether the plan meets promised delivery windows.

The goal is to showcase how the larger architecture could behave without
pulling in heavy dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
import math
import random
import argparse
import json
import copy


# ----------------------- Domain Models ----------------------- #


@dataclass
class Location:
    label: str
    coord: Tuple[float, float]
    zone: str


@dataclass
class Order:
    id: str
    pickup: Location
    dropoff: Location
    promise_by: datetime
    priority: str
    handling: str
    weight_kg: float


@dataclass
class Driver:
    id: str
    mode: str
    speed_kmph: float
    capacity: int
    max_payload_kg: float
    shift_end: datetime
    location: Location
    assigned: List[Order] = field(default_factory=list)

    def remaining_capacity(self) -> int:
        return self.capacity - len(self.assigned)

    def remaining_payload(self) -> float:
        used = sum(order.weight_kg for order in self.assigned)
        return self.max_payload_kg - used


# ----------------------- Helper Functions ----------------------- #


def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.dist(p1, p2)


def tile_for_point(point: Tuple[float, float]) -> str:
    x, y = point
    if x < 4 and y < 4:
        return "core"
    if x >= 4 and y < 4:
        return "waterfront"
    if x < 4 and y >= 4:
        return "uptown"
    return "north"


# ----------------------- Agents ----------------------- #


UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC)


class OrderIntakeAgent:
    def ingest(self, payloads: Iterable[Dict]) -> List[Order]:
        orders: List[Order] = []
        base_time = utcnow()
        for raw in payloads:
            pickup = self._build_location(raw["pickup_label"], raw["pickup_coord"])
            dropoff = self._build_location(raw["dropoff_label"], raw["dropoff_coord"])
            promise_by = base_time + timedelta(minutes=raw["promise_minutes"])
            order = Order(
                id=raw["id"],
                pickup=pickup,
                dropoff=dropoff,
                promise_by=promise_by,
                priority=raw.get("priority", "standard"),
                handling=raw.get("handling", "standard"),
                weight_kg=raw.get("weight_kg", 2.0),
            )
            orders.append(order)
        return orders

    def _build_location(self, label: str, coord: Tuple[float, float]) -> Location:
        point = tuple(coord)
        return Location(label=label, coord=point, zone=tile_for_point(point))


class CapacityAgent:
    def __init__(self, drivers: List[Driver]) -> None:
        self._drivers = drivers

    def available_drivers(self) -> List[Driver]:
        now = utcnow()
        return [copy.deepcopy(driver) for driver in self._drivers if driver.shift_end > now]


class SignalAgent:
    def __init__(self, seed: int = 42) -> None:
        self._rand = random.Random(seed)

    def hazard_map(self, orders: Iterable[Order]) -> Dict[str, float]:
        zones = {order.pickup.zone for order in orders} | {order.dropoff.zone for order in orders}
        return {zone: 1.0 + self._rand.uniform(0, 0.6) for zone in zones}


class PlannerAgent:
    PRIORITY_WEIGHTS = {"priority": 2.0, "sla_plus": 1.5, "standard": 1.0}

    def assign_orders(self, orders: List[Order], drivers: List[Driver]) -> Dict[str, List[Order]]:
        assignment: Dict[str, List[Order]] = {driver.id: [] for driver in drivers}
        scored_orders = sorted(orders, key=self._priority_score, reverse=True)
        for order in scored_orders:
            driver = self._choose_driver(order, drivers)
            if driver:
                driver.assigned.append(order)
                assignment[driver.id].append(order)
        return assignment

    def _priority_score(self, order: Order) -> float:
        weight = self.PRIORITY_WEIGHTS.get(order.priority, 1.0)
        time_to_promise = (order.promise_by - utcnow()).total_seconds() / 60
        urgency = max(1.0, 60 / (time_to_promise + 1))
        return weight * urgency

    def _choose_driver(self, order: Order, drivers: List[Driver]) -> Driver | None:
        best_driver: Driver | None = None
        best_cost = float("inf")
        for driver in drivers:
            if driver.remaining_capacity() <= 0:
                continue
            if driver.remaining_payload() < order.weight_kg:
                continue
            distance = euclidean_distance(driver.location.coord, order.pickup.coord)
            depth_penalty = len(driver.assigned) * 5
            cost = distance + depth_penalty
            if cost < best_cost:
                best_cost = cost
                best_driver = driver
        return best_driver


class RouteOptimizationAgent:
    MODE_SPEED_ADJUST = {"bike": 0.8, "van": 1.0, "robot": 0.5}

    def build_routes(
        self,
        assignment: Dict[str, List[Order]],
        drivers: Dict[str, Driver],
        hazard_map: Dict[str, float],
    ) -> Dict[str, List[Dict]]:
        routes: Dict[str, List[Dict]] = {}
        for driver_id, orders in assignment.items():
            driver = drivers[driver_id]
            current = driver.location.coord
            current_time = utcnow()
            route_steps: List[Dict] = []
            for order in sorted(orders, key=lambda o: o.promise_by):
                travel_pickup = self._travel_time_hours(current, order.pickup.coord, driver, hazard_map)
                current_time += timedelta(hours=travel_pickup)
                route_steps.append(
                    {
                        "type": "pickup",
                        "order_id": order.id,
                        "eta": current_time,
                        "location": order.pickup.label,
                    }
                )
                current = order.pickup.coord
                travel_dropoff = self._travel_time_hours(current, order.dropoff.coord, driver, hazard_map)
                current_time += timedelta(hours=travel_dropoff)
                route_steps.append(
                    {
                        "type": "dropoff",
                        "order_id": order.id,
                        "eta": current_time,
                        "location": order.dropoff.label,
                        "promise_by": order.promise_by,
                    }
                )
                current = order.dropoff.coord
            routes[driver_id] = route_steps
        return routes

    def _travel_time_hours(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        driver: Driver,
        hazard_map: Dict[str, float],
    ) -> float:
        distance = euclidean_distance(start, end)
        hazard = hazard_map.get(tile_for_point(end), 1.0)
        mode_adjust = self.MODE_SPEED_ADJUST.get(driver.mode, 1.0)
        effective_speed = driver.speed_kmph * mode_adjust / hazard
        if effective_speed == 0:
            return 0
        return distance / effective_speed


class SLAGuardianAgent:
    def build_report(self, routes: Dict[str, List[Dict]]) -> List[Dict]:
        report: List[Dict] = []
        for driver_id, steps in routes.items():
            for step in steps:
                if step["type"] != "dropoff":
                    continue
                lateness = (step["eta"] - step["promise_by"]).total_seconds() / 60
                report.append(
                    {
                        "driver_id": driver_id,
                        "order_id": step["order_id"],
                        "eta": step["eta"],
                        "promise_by": step["promise_by"],
                        "status": "late" if lateness > 0 else "on_time",
                        "minutes_delta": round(lateness, 1),
                    }
                )
        return report


# ----------------------- Demo Data ----------------------- #


def demo_orders() -> List[Dict]:
    return [
        {
            "id": "ORD-100",
            "pickup_label": "Micro-fulfillment A",
            "pickup_coord": (1.5, 1.0),
            "dropoff_label": "Customer Midtown",
            "dropoff_coord": (3.5, 4.0),
            "promise_minutes": 60,
            "priority": "priority",
            "handling": "cold_chain",
        },
        {
            "id": "ORD-101",
            "pickup_label": "Micro-fulfillment B",
            "pickup_coord": (5.0, 2.0),
            "dropoff_label": "Customer Waterfront",
            "dropoff_coord": (6.0, 1.0),
            "promise_minutes": 90,
            "priority": "standard",
            "weight_kg": 25,
        },
        {
            "id": "ORD-102",
            "pickup_label": "Dark Store South",
            "pickup_coord": (2.0, 5.5),
            "dropoff_label": "Customer Uptown",
            "dropoff_coord": (1.0, 6.0),
            "promise_minutes": 45,
            "priority": "sla_plus",
        },
        {
            "id": "ORD-103",
            "pickup_label": "Warehouse West",
            "pickup_coord": (4.5, 4.5),
            "dropoff_label": "Customer North",
            "dropoff_coord": (6.0, 6.0),
            "promise_minutes": 120,
            "weight_kg": 35,
        },
        {
            "id": "ORD-104",
            "pickup_label": "Ghost Kitchen",
            "pickup_coord": (3.0, 2.0),
            "dropoff_label": "Office Hub",
            "dropoff_coord": (2.5, 3.0),
            "promise_minutes": 35,
            "priority": "priority",
        },
    ]


def demo_drivers() -> List[Driver]:
    now = utcnow()
    return [
        Driver(
            id="DRV-1",
            mode="van",
            speed_kmph=35,
            capacity=4,
            max_payload_kg=120,
            shift_end=now + timedelta(hours=6),
            location=Location("Depot Central", (2.0, 2.0), zone="core"),
        ),
        Driver(
            id="DRV-2",
            mode="bike",
            speed_kmph=18,
            capacity=3,
            max_payload_kg=30,
            shift_end=now + timedelta(hours=4),
            location=Location("Bike Hub Waterfront", (5.5, 2.5), zone="waterfront"),
        ),
        Driver(
            id="DRV-3",
            mode="robot",
            speed_kmph=10,
            capacity=2,
            max_payload_kg=15,
            shift_end=now + timedelta(hours=8),
            location=Location("Robot Dock Uptown", (1.0, 5.0), zone="uptown"),
        ),
    ]


# ----------------------- Fixture Loading & Updates ----------------------- #


def load_orders_from_file(path: Path, intake_agent: OrderIntakeAgent) -> List[Order]:
    payloads = json.loads(path.read_text())
    if not isinstance(payloads, list):
        raise ValueError("Orders file must contain a list of payloads")
    return intake_agent.ingest(payloads)


def load_drivers_from_file(path: Path) -> List[Driver]:
    payloads = json.loads(path.read_text())
    if not isinstance(payloads, list):
        raise ValueError("Drivers file must contain a list of driver definitions")
    now = utcnow()
    drivers: List[Driver] = []
    for raw in payloads:
        loc = raw["location"]
        coord = tuple(loc["coord"])
        location = Location(label=loc["label"], coord=coord, zone=tile_for_point(coord))
        shift_hours = raw.get("shift_hours", 6)
        driver = Driver(
            id=raw["id"],
            mode=raw.get("mode", "van"),
            speed_kmph=raw.get("speed_kmph", 30),
            capacity=raw.get("capacity", 4),
            max_payload_kg=raw.get("max_payload_kg", 100),
            shift_end=now + timedelta(hours=shift_hours),
            location=location,
        )
        drivers.append(driver)
    return drivers


def order_update_events() -> List[Dict]:
    return [
        {"type": "upgrade", "order_id": "ORD-101", "new_priority": "priority"},
        {
            "type": "add",
            "payload": {
                "id": "ORD-200",
                "pickup_label": "Fresh Hub East",
                "pickup_coord": (3.5, 1.0),
                "dropoff_label": "Hospital ER",
                "dropoff_coord": (2.0, 2.5),
                "promise_minutes": 25,
                "priority": "priority",
                "handling": "med_specimen",
                "weight_kg": 12,
            },
        },
    ]


def apply_order_updates(orders: List[Order], intake_agent: OrderIntakeAgent) -> Tuple[List[Order], List[str]]:
    updated_orders = copy.deepcopy(orders)
    notes: List[str] = []
    events = order_update_events()
    order_index = {order.id: order for order in updated_orders}
    for event in events:
        if event["type"] == "upgrade":
            order = order_index.get(event["order_id"])
            if order:
                order.priority = event["new_priority"]
                notes.append(f"Upgraded {order.id} to {order.priority}")
        elif event["type"] == "add":
            new_order = intake_agent.ingest([event["payload"]])[0]
            updated_orders.append(new_order)
            notes.append(f"Inserted rush order {new_order.id}")
    return updated_orders, notes


# ----------------------- Orchestrator ----------------------- #


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LastMile orchestration proof-of-concept")
    parser.add_argument("--orders-file", type=Path, help="Path to JSON list of order payloads")
    parser.add_argument("--drivers-file", type=Path, help="Path to JSON list of driver definitions")
    parser.add_argument("--skip-updates", action="store_true", help="Skip simulating dynamic updates")
    parser.add_argument("--hazard-seed", type=int, default=42, help="Seed for hazard randomization")
    return parser.parse_args()


def run_plan_cycle(
    label: str,
    orders: List[Order],
    driver_templates: List[Driver],
    signal_agent: SignalAgent,
    planner_agent: PlannerAgent,
    route_agent: RouteOptimizationAgent,
    sla_agent: SLAGuardianAgent,
    update_notes: List[str] | None = None,
) -> None:
    print(f"\n\n##### {label} #####")
    if update_notes:
        for note in update_notes:
            print(f"- {note}")

    capacity_agent = CapacityAgent(drivers=driver_templates)
    drivers = capacity_agent.available_drivers()
    hazard_map = signal_agent.hazard_map(orders)
    assignment = planner_agent.assign_orders(orders, drivers)
    drivers_by_id = {driver.id: driver for driver in drivers}
    routes = route_agent.build_routes(assignment, drivers_by_id, hazard_map)
    sla_report = sla_agent.build_report(routes)

    _print_plan(label, hazard_map, assignment, routes, sla_report)


def run_demo(args: argparse.Namespace) -> None:
    intake_agent = OrderIntakeAgent()
    planner_agent = PlannerAgent()
    route_agent = RouteOptimizationAgent()
    sla_agent = SLAGuardianAgent()
    signal_agent = SignalAgent(seed=args.hazard_seed)

    orders = (
        load_orders_from_file(args.orders_file, intake_agent)
        if args.orders_file
        else intake_agent.ingest(demo_orders())
    )
    drivers_template = (
        load_drivers_from_file(args.drivers_file) if args.drivers_file else demo_drivers()
    )

    run_plan_cycle(
        "Initial Plan",
        orders,
        drivers_template,
        signal_agent,
        planner_agent,
        route_agent,
        sla_agent,
    )

    if not args.skip_updates:
        updated_orders, notes = apply_order_updates(orders, intake_agent)
        run_plan_cycle(
            "After Dynamic Updates",
            updated_orders,
            drivers_template,
            signal_agent,
            planner_agent,
            route_agent,
            sla_agent,
            update_notes=notes,
        )


def _print_plan(
    label: str,
    hazard_map: Dict[str, float],
    assignment: Dict[str, List[Order]],
    routes: Dict[str, List[Dict]],
    sla_report: List[Dict],
) -> None:
    print("\n=== Hazard Map ===")
    for zone, hazard in hazard_map.items():
        print(f"{zone:<12} multiplier={hazard:.2f}")

    print("\n=== Assignments ===")
    for driver_id, orders in assignment.items():
        if not orders:
            continue
        summaries = ", ".join(f"{order.id}({order.priority})" for order in orders)
        print(f"{driver_id}: {summaries}")

    print("\n=== Routes & ETAs ===")
    for driver_id, steps in routes.items():
        print(f"\nDriver {driver_id}")
        for step in steps:
            eta = step['eta'].strftime("%H:%M:%S")
            if step["type"] == "pickup":
                print(f"  - Pickup {step['order_id']} at {step['location']} ETA {eta}")
            else:
                promise = step["promise_by"].strftime("%H:%M:%S")
                print(
                    f"  - Dropoff {step['order_id']} at {step['location']} ETA {eta} (promise {promise})"
                )

    print("\n=== SLA Report ===")
    for entry in sla_report:
        delta = entry["minutes_delta"]
        status = entry["status"]
        print(
            f"{entry['order_id']} via {entry['driver_id']} -> {status} ({delta:+.1f} min vs promise)"
        )


if __name__ == "__main__":
    run_demo(parse_args())
