# LastMile AI Delivery Network

## Problem Statement
Urban and suburban retailers rely on a mesh of couriers, gig drivers, and micro-fulfillment centers to satisfy same-day and sub-hour deliveries. Demand spikes, diverse customer promises (priority, temperature control, signature), and highly dynamic traffic compromise on-time performance and delivery cost. The goal is to build an AI-native orchestration platform that continuously plans, schedules, and executes last-mile deliveries by coordinating specialized agents.

## Goals & Non-Goals
- **Goals**
  - Hit >97% on-time delivery across standard, priority, and SLA-plus tiers.
  - Reduce cost per drop by ≥12% via consolidated routing and vehicle utilization.
  - Provide APIs for retailers and courier partners to publish orders, capacity, and constraints in near real-time.
  - Support human control center visibility with explainable agent decisions and override hooks.
- **Non-Goals**
  - Building the in-store picking or warehouse management system.
  - Optimizing the long-haul or middle-mile leg.
  - Owning telematics hardware; we integrate with partner feeds.

## Key Requirements
1. **Dynamic scheduling**: respond to new/changed orders within 30 seconds while preserving feasibility for existing routes.
2. **Priority-aware dispatch**: high-value orders may preempt other jobs and trigger re-optimization.
3. **Traffic/weather adaptation**: consume third-party feeds and adjust ETAs, driver assignment, or sequence.
4. **Multi-modal fleet**: bikes, vans, autonomous bots with different capacity, speed, and regulatory constraints.
5. **Compliance & safety**: ensure cold-chain and proof-of-delivery requirements; enforce driver hours and zoning rules.
6. **Explainability**: capture reasoning steps for dispute handling.
7. **Resilience**: degrade gracefully if an agent or data source is unavailable.

## High-Level Architecture
```
Retailer APIs -> Order Intake Agent -> Order Store (Postgres)
                                   -> Constraint Repository (Redis + Feature Store)
Supply Integrations -> Capacity Agent -> Driver Graph (Neo4j)
Traffics/Weather -> Signal Agent -> Event Stream (Kafka)

Central Orchestrator (workflow engine)
  |- Demand Forecast Agent
  |- Planner Agent (macro assignment)
  |- Route Optimization Agent
  |- SLA Guardian Agent
  |- Exception Agent (alerts, re-plan)

Execution Layer
  |- Mobile SDK / Courier App
  |- Customer Tracking APIs
  |- Control Center UI
```
Agents communicate over Kafka topics and share artifacts in an S3-compatible object store.

## Agent Responsibilities
- **Order Intake Agent**: validates payloads, enriches with geocoding, decomposes bundles (e.g., multi-drop). Emits `order.created`.
- **Capacity Agent**: aggregates driver schedules, vehicle attributes, regulatory flags. Maintains a bipartite graph of drivers ↔ service regions.
- **Signal Agent**: fuses real-time traffic, weather, and municipal alerts into a normalized hazard score per geo-tile and time bucket.
- **Demand Forecast Agent**: short-term (0-6h) forecasting using temporal fusion transformers to pre-allocate vehicles in hot zones.
- **Planner Agent**: solves mixed integer optimization for assigning orders to vehicles considering priority, shift windows, and capacity. Produces candidate batches for the Route Optimization Agent.
- **Route Optimization Agent**: runs a hybrid heuristic (ALNS + deep Q-learning) to sequence stops, estimate ETAs, and compute slack. Emits routes with confidence intervals.
- **SLA Guardian Agent**: continuously monitors execution telemetry; if forecasted lateness exceeds threshold, it triggers exception flows (reassignment, micro-fulfillment re-routing, customer comms).
- **Exception Agent**: reasons about disruptions (vehicle breakdown, road closure) and escalates to human operators with prescriptive actions.
- **Control Center Copilot**: generative agent that explains plan impacts, surfaces "what-if" scenarios, and assists manual overrides.

## Data Model Highlights
- **Orders Table (Postgres)**: id, pickup/dropoff geo, promised window, priority tier, handling requirements, weight/volume, penalties.
- **Drivers Graph (Neo4j)**: nodes for drivers, vehicles, service zones; edges for eligibility, shift membership, certifications.
- **Telemetry Stream (Kafka)**: driver_id, location, speed, load factor, trust score, hazard score, predicted ETA.
- **Feature Store (Feast)**: historical dwell times, curb availability, driver reliability; used by agents for learning and constraints.

## Workflows
1. **New Order Flow**
   1. Order Intake validates and persists order.
   2. Planner fetches available capacity and forecasts demand for that zone.
   3. Planner produces candidate assignments; Route Optimization finalizes sequences.
   4. SLA Guardian records baseline ETA and notifies customer tracking endpoint.
2. **Mid-Route Priority Upgrade**
   1. Retailer calls `/orders/{id}/upgrade`.
   2. Planner marks high priority, re-optimizes impacted routes.
   3. SLA Guardian sends predictive delay notices to affected customers.
3. **Disruption Handling**
   1. Signal Agent posts hazard spike for a tile.
   2. Exception Agent runs scenario simulation (reroute vs. swap driver).
   3. If confidence > threshold, orchestrator executes reroute; otherwise, escalate to human with suggested action.

## Algorithms & Techniques
- **Assignment**: MILP solved via OR-Tools/Pyomo with warm-start from previous plan, prioritized by penalty-weighted objective.
- **Routing**: Adaptive Large Neighborhood Search seeded by graph neural network that scores next-stop choices; reinforcement learning policy refines decisions during execution.
- **ETA Prediction**: gradient boosted models with features from historical telemetry and live hazard scores; fallback to deterministic travel time tables.
- **Anomaly Detection**: streaming autoencoders over telemetry detect behavior drift; triggers compliance checks.

## Scalability & Reliability
- Kafka partitions per metro keep agent streams isolated; planner pods scale with KEDA on backlog depth.
- Dual-region Postgres with logical replication; read replicas feed analytics.
- Route Optimization Agent runs on GPU-enabled nodes for RL inference; warm pool maintained via cluster autoscaler.
- Fallback modes: if Route Optimization offline, degrade to deterministic heuristics; if Signal Agent fails, use historical averages.

## Security & Compliance
- Orders contain PII; use field-level encryption and scoped IAM policies.
- Courier app uses mutual TLS and short-lived OAuth tokens.
- Audit log captures agent decisions (input features, chosen action, confidence) for regulatory review.

## Observability
- OpenTelemetry spans per orchestration workflow.
- KPI dashboards: SLA attainment, cost per drop, re-plan frequency, agent uptime.
- Incident playbooks tied to alerting policies for SLA Guardian and Exception Agent.

## Open Questions
- How to incentivize drivers for AI-generated micro-tasks (e.g., repositioning) without hurting acceptance rates?
- Should we support federated learning for ETA models to respect courier data ownership?
- Optimal balance between human overrides vs. full autonomy in dense urban cores.
