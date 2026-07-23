# Phase 4 Milestone 1: Analytics Import Foundation

## Purpose

This milestone gives AuraAI a founder-controlled, local-only way to record
source-reported measurements for a confirmed publication. It stores evidence;
it does not interpret analytics, recommend actions, score content, trigger
learning, or advance a mission.

## Architecture

The import path reuses existing authority boundaries:

1. The founder opens the analytics page in the existing dashboard.
2. The dashboard reads the canonical mission, publication record, publishing
   queue item, and analytics history from Mission Control.
3. A CSRF-protected form submits an explicitly UTC observation timestamp and
   typed metrics.
4. `MissionCommandService` delegates to `MissionControlService`.
5. Mission Control validates publication identity and import semantics.
6. The repository stores the snapshot and Mission Control appends one import
   event in the same transaction.

No browser automation, provider call, crawl, render, upload, or publish
operation occurs.

## AnalyticsMetrics

`AnalyticsMetrics` is an immutable Pydantic domain model. Count and duration
fields are optional non-negative integers. Revenue is an optional finite,
non-negative `Decimal`.

Revenue amount and currency are coupled in both directions. Currency is
normalized to uppercase and must contain exactly three ASCII letters. Unknown
fields are rejected through `AuraBaseModel`. An import note may accompany
measurements, but a note alone is not analytics evidence: at least one numeric
metric or revenue amount is required. Zero is a valid measurement and remains
distinct from an omitted value.

## AnalyticsSnapshot

`AnalyticsSnapshot` is immutable and binds:

- snapshot, mission, publication, and queue-item identities;
- publication destination;
- observation and import timestamps;
- importing actor;
- canonical payload hash; and
- validated metrics.

Destination and actor follow the existing publication-domain length
constraints. The payload hash is a lowercase 64-character SHA-256 value.

## Durable observation identity

One durable observation is identified by:

```text
(publication_id, observed_at)
```

SQLite enforces this with a unique constraint. The in-memory repository
enforces the same identity. Snapshot ID remains the record identity, while the
publication/observation pair defines idempotency.

## Payload hash and Decimal normalization

Mission Control serializes metrics with sorted keys and compact separators,
then computes SHA-256. Revenue `Decimal` values are normalized before hashing,
so numerically equivalent values such as `10.50` and `10.5` produce the same
payload hash.

The hash distinguishes an identical retry from contradictory evidence at the
same durable observation identity.

## UTC timestamp rules

`observed_at` and `imported_at` must be timezone-aware and have a zero UTC
offset. Naive timestamps and non-zero offsets are rejected rather than assumed
or converted.

Accepted timestamps are represented canonically in UTC. The form requires an
explicit `Z` or `+00:00` timezone. An observation exactly five minutes ahead of
the Mission Control clock is accepted; any value further ahead is rejected.

Persistence, events, dashboard projections, and templates use ISO-8601 values
from the canonical UTC datetimes.

## Repository schema

SQLite stores analytics in `analytics_snapshots`:

```text
id                  TEXT PRIMARY KEY
mission_id          TEXT, foreign key to missions
publication_id      TEXT, foreign key to publication_records
queue_item_id       TEXT, foreign key to publishing_queue
destination         TEXT
observed_at         TEXT
imported_at         TEXT
payload_hash        TEXT
data                TEXT, serialized AnalyticsSnapshot
UNIQUE(publication_id, observed_at)
```

Publication history has an index beginning with `publication_id` and
`observed_at DESC`. Reads are ordered by `observed_at DESC`,
`imported_at DESC`, and snapshot ID descending.

## Exception translation

SQLite details remain inside `SQLiteMissionControlRepository`.

- The expected observation uniqueness collision becomes
  `DuplicateRecordError`.
- Other SQLite integrity failures become `RepositoryIntegrityError`.
- A duplicate reported by the repository without a reloadable winner becomes
  `RepositoryConsistencyError`.

The HTTP boundary returns safe status codes and does not expose database error
details.

## Idempotency, conflicts, and collision recovery

Before insertion, Mission Control looks up the durable observation identity.
An identical payload hash returns the stored snapshot. A different hash raises
`ConflictingDecisionError`.

The first import inserts the snapshot and appends
`analytics.snapshot_imported` in one repository transaction.

If concurrent writers collide, the losing operation reloads the winner:

- matching hash returns the winner;
- different hash raises a conflict; and
- a missing winner fails closed with `RepositoryConsistencyError`.

The losing transaction does not append a duplicate event.

## Event behavior

`analytics.snapshot_imported` records:

- analytics snapshot ID;
- mission ID;
- publication ID;
- queue item ID;
- destination;
- observed and imported timestamps;
- actor; and
- payload hash.

An idempotent retry does not create another event.

## Command boundary

`MissionCommandService.import_analytics_snapshot` requires a non-empty actor
and delegates to Mission Control. Mission Control remains authoritative for
timestamp skew, publication identity, confirmed publication state,
idempotency, conflict handling, persistence, and events.

## CSRF behavior

The local dashboard uses its existing double-submit CSRF mechanism. The GET
route creates a random token, places it in an HTTP-only, same-site cookie, and
places the same token in the form. The POST route requires exactly one form
value and compares it with the cookie using a constant-time comparison.

The token is removed at the form boundary and is never passed into
`AnalyticsMetrics`.

## Dashboard routes

The GET and POST routes are:

```text
GET  /missions/{mission_id}/publications/{publication_id}/analytics/import
POST /missions/{mission_id}/publications/{publication_id}/analytics/import
```

The GET route validates the persisted mission, publication, mission binding,
queue item, and existing operations projection. It supplies standard dashboard
context, the CSRF token, canonical records, and current analytics history.

The POST route accepts only bounded URL-encoded form input, rejects repeated or
unknown fields, parses explicit UTC timestamps, validates metrics, verifies
CSRF, and delegates through the existing command boundary.

## Dashboard projection

`DashboardPublicationAnalytics` contains typed `AnalyticsSnapshot` values:

- latest snapshot;
- historical snapshots;
- snapshot count;
- latest observed/imported timestamps;
- evidence-presence flag;
- actionability flag; and
- explicit blocking reason.

The projection reads canonical repository state. Templates display it without
deriving business rules.

## Exclusions

This milestone does not:

- interpret metrics;
- calculate performance scores;
- recommend content or business actions;
- update mission learning;
- advance mission state;
- browse or crawl;
- invoke providers;
- render;
- upload; or
- publish.

## Test coverage

Focused tests cover domain constraints, Decimal hashing, UTC validation and
clock skew, repository parity, SQLite translation, identity validation,
idempotency and collision recovery, CSRF, strict form parsing, safe HTTP
mapping, GET rendering and not-found behavior, typed dashboard projection,
empty history, deterministic ordering, and rendered history.

The repository, dashboard, command, runtime composition, and complete project
test suites are also run before milestone completion.

## Known limitations

- Imports are local founder actions; there is no multi-user identity system.
- Measurements are manually entered and are not independently verified.
- The schema stores source-reported evidence but does not yet model source API
  provenance beyond the confirmed publication identity.
- Analytics interpretation and mission learning are deliberately deferred to
  later, separately approved milestones.
