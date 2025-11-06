# Key Workflow Sequences

## 1. Recording Session to Guide Creation

```
Recorder Agent -> Ingestion Gateway: Device OAuth token + start_session
Ingestion Gateway -> Auth Service: validate token (mTLS)
Auth Service -> Ingestion Gateway: ok(session_id, presigned_keys)
Ingestion Gateway -> Recorder Agent: session_id, upload_url, encryption_material

loop per event batch
  Recorder Agent -> Ingestion Gateway: EventBatch(session_id, encrypted_events)
  Ingestion Gateway -> Kafka (events topic): publish(batch, tenant_id, session_id)
  Stream Processor -> LiveSessions store: update_preview(step_state)
  Stream Processor -> Websocket Hub: emit preview_update
  Web Editor <- Websocket Hub: preview update (step text, thumbnail)
end

Recorder Agent -> Ingestion Gateway: finalize(session_id)
Stream Processor -> AI Service: summarize_steps(session_id)
AI Service -> Stream Processor: step summaries, redaction hints
Stream Processor -> Guide Store: persist metadata (Aurora), content (DynamoDB), media refs (S3)
Stream Processor -> Audit Log svc: record guide_created
Stream Processor -> Notification svc: emit guide_ready + preview URL
Recorder Agent <- Ingestion Gateway: finalize_ack(guide_id, version)
```

## 2. Collaborative Editing Session

```
User A Browser -> Collaboration API: open guide (JWT Bearer)
Collaboration API -> AuthZ svc: check permissions (Editor)
Collaboration API -> Guide Store: fetch latest version (Aurora + Dynamo)
Collaboration API -> User A Browser: initial document + web socket token

User A Browser -> Realtime Hub: join document channel (CRDT)
User B Browser -> Collaboration API/Realtime Hub: same as above

loop per edit
  User A Browser -> Realtime Hub: change delta
  Realtime Hub -> Conflict Resolver (CRDT): merge & broadcast
  Realtime Hub -> User B Browser: delta
  Realtime Hub -> Collaboration API: persist delta (version WAL)
  Collaboration API -> Guide Store: append new version snapshot periodically
end

Collaboration API -> Audit Log: record edit events
```

## 3. Guide Sharing & Access

```
Publisher -> Collaboration API: publish(guide_id, visibility=tenant)
Collaboration API -> Policy Engine: validate share policy
Collaboration API -> Guide Store: mark version published, generate signed media URLs
Collaboration API -> CDN: invalidate cache paths
Collaboration API -> Notification svc: notify followers / integrations

Viewer -> Edge CDN: GET /guides/{slug}
Edge CDN -> Auth Gateway: validate token (if private)
Edge CDN -> Guide Cache (Redis): fetch metadata
Guide Cache -> DynamoDB: cache miss -> fetch steps
Edge CDN -> S3 (signed URLs): retrieve media assets
Viewer <- Edge CDN: rendered guide payload

Analytics Collector -> Kafka (analytics): view event
Analytics Pipeline -> Lake: append usage metrics
```
