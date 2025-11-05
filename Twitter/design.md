# Twitter-Scale Microblogging Platform Design

## 1. Problem Statement
Design a Twitter-like, planet-scale microblogging platform that supports:
- Posting short messages (tweets) with media attachments.
- Following other users to receive their updates.
- Fan-out timelines (home feeds) with near-real-time delivery.
- Public profiles, mentions, hashtags, likes, retweets, and search.
- High availability (99.99%+), low latency (<200 ms P99 for home timeline reads), and strong abuse mitigation.

The solution needs to scale to hundreds of millions of daily active users (DAU), tens of millions of QPS peak for reads, and millions of writes per minute across global regions.

## 2. Requirements and Scope

### Functional
- Create tweets up to 280 chars (text, emojis, media).
- Fetch home timeline (reverse chronological) for authenticated user.
- Fetch user profile timeline.
- Follow/unfollow users and organizations.
- Like, retweet, reply to tweets.
- Hashtag, full-text, and user search.
- Notifications for mentions, follows, likes, retweets.
- Trending topics per geography.
- Moderation: spam detection, rate controls, account suppression.

### Non-Functional
- Multi-region active-active serving, 99.99% availability for core read APIs.
- P95 read latency < 150 ms, write latency < 500 ms.
- Durable storage (11 9s). Tweets immutable after creation.
- Horizontal scalability on commodity hardware.
- Privacy and compliance (GDPR, CCPA), data residency where required.
- Graceful degradation when dependent subsystems fail.

### Out of Scope (initial release)
- Long-form content, Spaces, algorithmic ranking (stick to recency + light ranking signals).
- Ad serving pipeline.
- Third-party API ecosystem.

## 3. Capacity Planning and Workload Estimation
Assume:
- 300M DAU, 60% mobile, 40% web.
- Avg 6 tweets/user/day → ~1.8B tweets/day (~21K writes/sec sustained, 4x bursts).
- Each user follows avg 200 accounts. Home feed pull happens ~20 times/day → 6B timeline reads/day (~70K reads/sec sustained, 5x bursts).
- Likes/retweets roughly 5x tweets → ~100K writes/sec peak.
- Media uploads ~25% of tweets; handled via separate media service and CDN.

Storage projections (yearly):
- Tweets: 280 chars ≈ 280 bytes text + metadata (~200 bytes) → 480 bytes/tweet → 864 TB/year.
- Indices (inverted, graph, engagement) add ~3x overhead → ~2.5 PB/year.

## 4. API Surface (REST + gRPC)
- `POST /api/v1/tweets` `CreateTweetRequest { user_id, text, media_ids[], visibility }`
- `GET /api/v1/users/{id}/tweets?cursor=...`
- `GET /api/v1/home_timeline?user_id&cursor=...`
- `POST /api/v1/users/{id}/follow` / `DELETE ...`
- `POST /api/v1/tweets/{id}/like` / `DELETE ...`
- `POST /api/v1/tweets/{id}/retweet`
- `GET /api/v1/search?q&filters`
- `GET /api/v1/trends?location`

All APIs exposed via API Gateway with OAuth 2.0 / mTLS, rate limiting, request auth metadata propagation.

## 5. High-Level Architecture
```
        Clients (mobile, web, partners)
                    │
             API Gateway / Edge
          (AuthN/Z, rate limits, WAF)
                    │
        ┌───────────┴───────────┐
        │                       │
 Tweet Write Path          Read Path
        │                       │
 Tweet Service          Timeline Service
 (stateless pods)       (fan-out & fan-in)
        │                       │
  Kafka (Durable Log)   Cache (Redis/Memcached)
        │                       │
 Write DB (Cassandra)   Timeline Stores
        │                (RocksDB / Cassandra)
 Media Service          Search Index (Elastic)
 Graph Service          User Service
 Notifications          Analytics / ML
```

### Key Components
- **API Gateway**: Envoy or NGINX with Lua filters for auth, per-endpoint quotas, geo-routing.
- **Tweet Service**: Validates payload, attaches metadata (ID, timestamps, geo), enqueues to Kafka, returns tweet ID. Stateless microservice with idempotent handling (client tokens, dedup store).
- **Timeline Service**:
  - **Fan-out-on-write** for heavy posters: On tweet creation, push tweet refs into followers' home timeline shards using async workers. Batched writes to Redis sorted sets + Cassandra partitions.
  - **Fan-out-on-read** for celebrities: Maintain live sets of latest tweets, merge at read time using `k-way merge`. Avoid pushing to millions of followers.
- **User Graph Service**: Manages follow relationships; stored in sharded graph store (e.g., RocksDB or Scylla). Provides high QPS neighbor fetch, strongly consistent writes.
- **Engagement Service**: Likes/retweets counters via write-through cache + eventual consistency to primary store.
- **Search & Trends**: Tweets streamed to pipeline (Kafka → Flink) for tokenization, inverted index updates, trending aggregates.
- **Media Service**: Handles uploads, stores in object storage (S3/GCS), serves via CDN, stores metadata pointer in Tweet.
- **Notification Service**: Subscribes to engagement events, dispatch push/mobile notifications via external providers.
- **Moderation Pipeline**: Real-time classification (abuse, spam). Kafka stream through ML inference service, quarantine service for flagged tweets.

## 6. Data Modeling

### Tweet Entity (Cassandra)
Partition key: `(author_id, bucket)`; clustering: `created_at desc`.
Columns: `tweet_id (timeuuid)`, `text`, `media_refs`, `visibility`, `metrics`, `state`.
Use time-bucket (daily) to keep partitions manageable (< 100MB).

### Home Timeline Store
Option A: Cassandra table `home_timeline_{shard}` with partition key `(user_id, shard_id)`, clustering `position desc`, values `tweet_ref`. Shard to limit partition size (use modulo of tweet_id).
Option B: Redis sorted set per user for latest 800 tweets, persist cold data to Cassandra for backfill.

### Social Graph
Store follow edges in two tables for directional lookups:
- `followers_{shard}(user_id, follower_id, state)`
- `followees_{shard}(user_id, followee_id, state)`

### Engagements
Counters via Cassandra table with lightweight transactions disabled; rely on atomic increments in Redis with periodic reconciliation job to Cassandra (CRDT counters).

### Search Index
Elasticsearch/OpenSearch cluster with data nodes per region. Tokenized documents referencing tweet_id, user_id, language, geo, hashtags.

## 7. Scaling and Partitioning
- **Sharding Keys**: Use consistent hashing on user_id for timeline and graph tables to distribute load evenly. Tweets sharded by author to keep locality.
- **Multi-Region Strategy**: Active-active with geo-partitioned writes (user affinity to home region). Use Kafka MirrorMaker or Pulsar geo-replication for cross-region streams. Cassandra multi-datacenter replication (LOCAL_QUORUM reads/writes).
- **Caching Layers**:
  - Layer 1: CDN for static assets, API caching for public tweets (Cache-Control).
  - Layer 2: Redis clusters for hot timelines, user lookups, tweet hydration.
- **Backpressure**: Kafka with topic-level quotas, consumer lag monitoring. Circuit breakers and rate limiting on API gateway and downstream services.

## 8. Consistency, Availability, Durability
- Choose AP (availability) over strong consistency for timelines. Tweets appear eventually for all followers; read-after-write on author timeline ensured via LOCAL_QUORUM write + read.
- Critical mutations (follow/unfollow) require strong consistency: use quorum writes and confirm via commit log (or leverage FoundationDB).
- Ensure idempotency tokens on write APIs to prevent duplicates on retries.
- Use event sourcing with Kafka as the source of truth for replay and audit.

## 9. Fault Tolerance and Disaster Recovery
- Zone-level redundancy: deploy services across ≥3 AZs per region.
- Cross-region failover: global traffic manager (DNS) with health-based routing; warm standby for critical stateful services.
- Automated backups: Cassandra snapshots daily + incremental. Kafka topic retention 7 days; archival to S3.
- Chaos testing regime (fault injection, partition). Run game days regularly.

## 10. Security and Compliance
- OAuth 2.0 / OpenID Connect for clients; service-to-service mTLS with SPIFFE identities.
- Encrypt data in transit (TLS 1.3) and at rest (KMS-managed keys).
- PII segmentation (user email, phone) in dedicated vault service. Differential privacy for analytics exports.
- Moderation controls: content classifiers, rate limiters, human review tools.
- Audit logging for privileged actions, fine-grained IAM (least privilege).

## 11. Observability
- Centralized logging (Loki/Elastic) with tracing (OpenTelemetry) and metrics (Prometheus). SLO dashboards per API (latency, error rate). Alerting on Kafka lag, cache hit-rate, DB saturation.
- Product analytics events to Snowflake/BigQuery via streaming pipelines.

## 12. Deployment and Delivery
- GitOps pipeline with canary deploys. Blue/green for stateless services, rolling for stateful.
- Feature flags (LaunchDarkly style) for incremental rollouts.
- Infra as code (Terraform) for clusters and data stores.

## 13. Edge Cases and Trade-offs
- **Celebrity fan-out**: Avoid sending to millions of timelines; rely on lazy fan-in merge, pre-computed slices.
- **Cold start timelines**: Blend global trending tweets with recommended follows.
- **Deleted/blocked content**: Maintain tombstone state; propagate deletes via Kafka to purge caches and search indexes.
- **Spam attacks**: Adaptive rate limits per IP/user; anomaly detection in stream pipeline.
- **Data residency**: Need per-country partitions; route EU users to EU region, replicate aggregated metrics only.

## 14. Iterative Delivery Plan (45-Minute Interview Outline)
1. Align on scope and constraints (3 min).
2. Capacity estimates & back-of-envelope math (5 min).
3. Present high-level architecture (10 min).
4. Deep dive on timeline construction, data storage, and fan-out strategies (15 min).
5. Discuss consistency, failure handling, and scaling (5 min).
6. Cover security, observability, trade-offs, future enhancements (5 min).
7. Quick recap & open questions (2 min).

## 15. Future Enhancements
- Personalized ranking signals (ML-based home timeline).
- Graph storage optimized with columnar adjacency lists (follow recommendations).
- Real-time Spaces/live audio integration.
- Monetization (ads, subscriptions), verified identity pipeline.

---

## Python Reference Implementation (MVP)
- Provides a simplified, single-node demonstration service consistent with the architecture:
  - In-memory timeline storage with fan-out on write for non-celebrity users.
  - Fan-in on read for users flagged as high-degree (followers > threshold).
  - Basic API endpoints via FastAPI (or fallback to pure Python HTTP server if frameworks unavailable).
  - Persistence abstraction to swap in real DBs.
- Focus is on clarity and extensibility rather than production-grade scale.
