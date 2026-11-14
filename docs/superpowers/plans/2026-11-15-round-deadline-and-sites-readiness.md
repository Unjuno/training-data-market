# Deadline integrity and deployment-readiness Implementation Plan

**Goal:** Make voting deadlines authoritative even if the worker is late; expose precise live status and protect natural-image publication by default.

**Architecture:** SQLite stores closes_at as part of immutable round metadata; the server rejects late mutations and the worker uses the persisted deadline. Frontend receives closes_at + server_time, renders an accessible countdown, and refreshes live status. Rights gating requires explicit manifest approval for CIFAR-10.

**Tech Stack:** Python 3.11+/FastAPI/SQLite/PyTorch, vanilla JS/node:test.

**Spec:** docs/spec-v0.4.md; docs/ux-quality-v0.7.md.

## Tasks
- [x] T1: Add failing tests for late votes/notes, legacy DB migration, next-round deadline, persisted worker deadline.
- [x] T2: Implement transactional `closes_at`, migrations, and deadline-aware worker; verify Python tests.
- [x] T3: Add failing tests for API clock/deadline, explicit dataset image-rights approval; implement gates; verify API tests.
- [x] T4: Add failing JS tests for countdown states; expose countdown and periodic status refresh in live UI; verify JS tests.
- [x] T5: Add local e2e script using HTTP requests through TestClient and real synthetic gradients, plus deployment runbook; verify both suites and static build.
- [ ] T6: Publish an isolated GitHub branch with reviewed changes and report exact tested vs untested conditions. Avoid claiming Sites itself was deployed.

## Global constraints
- Preserve data splits, 10-vote cap, 128 images / 40 steps, and no public CIFAR redistribution absent verified rights.
- Secrets never committed; demo remains loopback-only.
- No claims of verified CIFAR-10 accuracy without actual images.

## Review focus
- Worker outage after voting deadline must not allow late manipulation.
- Legacy databases migrate without discarding votes.
- Mobile clients with incorrect local clock still receive server-corrected deadline.
- Promotion rollback must not silently change original metrics.
- Natural-image endpoint never opens by environment flag alone.
