# Phase 4 Milestone 2: Deterministic Analytics Interpretation

## Purpose and scope

This milestone converts one immutable, durable `AnalyticsSnapshot` into one
immutable, durable `AnalyticsInterpretation`. The output explains only what the
available evidence supports.

```text
AnalyticsSnapshot
    ↓
AnalyticsInterpretation
    ↓
STOP
```

It does not recommend actions, store lessons, generate missions, progress
missions, choose niches or products, invoke providers, browse, render, upload,
or publish.

## Architecture

`mission_control.analytics_interpretation` is a pure deterministic engine. It
accepts a snapshot and supported ruleset, and returns a canonical typed
payload. It has no repository, HTTP, event, or wall-clock dependency.

`MissionControlService` is the authoritative write boundary. It loads the
durable source and related publication state, invokes the engine, calculates
the fingerprint, persists the interpretation, and appends the event in one
transaction. Repository implementations own storage and SQLite translation.
Commands and dashboard routes delegate without accepting caller-created
interpretation output.

## Evidence versus interpretation

Imported metrics remain immutable source evidence. Derived ratios exist only
inside `MetricInterpretation`; they are never written back into
`AnalyticsMetrics` or `AnalyticsSnapshot`.

`MetricEvidenceState` distinguishes:

- `AVAILABLE`: a non-zero source or derived value exists;
- `ZERO`: zero is explicitly observed evidence;
- `MISSING`: required source evidence was not supplied; and
- `NOT_APPLICABLE`: required evidence exists but a zero denominator makes a
  ratio mathematically inapplicable.

No missing value is invented.

## Domain models

The frozen, extra-field-rejecting domain contracts are:

- `MetricInterpretation`
- `InterpretationFinding`
- `AnalyticsInterpretation`
- `InterpretationClassification`
- `InterpretationConfidence`
- `MetricEvidenceState`

Every metric result records source metrics, a rule ID, evidence state,
classification, confidence, normalized value where available, and a
deterministic explanation. Findings remain traceable to the same rule and
evidence.

## Ruleset and classifications

The only supported version is:

```text
analytics-interpretation-v1
```

Raw totals have no universal baseline and always remain
`INSUFFICIENT_DATA`. Only mathematically valid ratios receive quality
classifications:

| Ratio | Outstanding | Strong | Average | Weak |
| --- | ---: | ---: | ---: | ---: |
| CTR or engagement | ≥ 0.1000 | ≥ 0.0500 | ≥ 0.0200 | < 0.0200 |

Overall classification is the conservative integer mean of available ratio
classification ranks. With no classifiable ratio, it is
`INSUFFICIENT_DATA`.

## Confidence

- `HIGH`: at least one ratio has every required source value and a non-zero
  denominator, so a direct versioned rule applies.
- `MEDIUM`: no ratio can be classified, but at least three numeric source
  metrics are explicitly present.
- `LOW`: evidence is sparse or ratios are missing/not applicable.

Confidence is evidence completeness, not an AI probability.

## Derived metrics, formulas, and rounding

Version 1 implements only:

```text
click_through_rate = clicks / impressions
engagement_rate = (likes + comments + shares + saves) / views
```

Engagement rate requires all four engagement components and views. Missing
inputs produce `MISSING`; a zero denominator produces `NOT_APPLICABLE`; a zero
numerator remains valid `ZERO` evidence.

Calculations use `Decimal` and quantize to `0.0001` with `ROUND_HALF_UP`.
Normalized Decimal text removes insignificant trailing zeroes.

## Conservative summaries and findings

Strengths contain only `STRONG` or `OUTSTANDING` ratio findings. Weaknesses
contain only `WEAK` ratio findings. Missing evidence contains missing source
metrics and missing/not-applicable ratios. Summary and explanation text come
from fixed templates and contain no recommendations.

## Ruleset versioning and payload hashing

Durable uniqueness is:

```text
(analytics_snapshot_id, ruleset_version)
```

A future ruleset can therefore create a new immutable interpretation without
overwriting prior history.

The SHA-256 payload hash covers canonical JSON containing the source snapshot
identity, ruleset version, classifications, confidence, metric
interpretations, findings, and summary. `interpreted_at` and actor are excluded
so retries remain idempotent. Decimal evidence is normalized before hashing,
making equivalent values such as `10.50` and `10.5` identical.

## Persistence schema and migration

SQLite schema version 3 adds `analytics_interpretations`:

```text
id                       TEXT PRIMARY KEY
mission_id               TEXT REFERENCES missions
publication_id           TEXT REFERENCES publication_records
queue_item_id             TEXT REFERENCES publishing_queue
analytics_snapshot_id    TEXT REFERENCES analytics_snapshots
destination              TEXT
ruleset_version          TEXT
interpreted_at           TEXT
actor                    TEXT
payload_hash             TEXT
data                     TEXT
UNIQUE(analytics_snapshot_id, ruleset_version)
```

An index supports publication history ordered by `interpreted_at DESC`, then
interpretation ID descending. Existing schema versions 1 and 2 are upgraded
non-destructively after tables and indexes are created. Existing analytics
evidence is not rebuilt or deleted.

The in-memory repository provides the same contract with defensive copies.
Expected uniqueness collisions become `DuplicateRecordError`; unrelated
SQLite integrity failures become `RepositoryIntegrityError`. SQLite never
leaks into Mission Control.

## Service validation and immutable sources

`MissionControlService.interpret_analytics_snapshot` validates:

- supported ruleset and non-empty actor;
- mission and snapshot existence;
- snapshot/mission identity;
- publication and queue existence;
- publication and queue mission identity;
- snapshot, publication, and queue relationships;
- destination consistency; and
- publication content hash versus queue manifest hash.

The operation does not update the snapshot, publication, queue, mission,
tasks, workflow, or mission status.

## Idempotency and concurrency

Before insertion, Mission Control loads the snapshot/ruleset identity.
Matching hash returns the existing interpretation. A different hash fails
closed with `ConflictingDecisionError`.

The first write stores the interpretation and appends `analytics.interpreted`
in one transaction. On a concurrent `DuplicateRecordError`, Mission Control
reloads the winner:

- matching hash returns the winner;
- conflicting hash raises `ConflictingDecisionError`; and
- missing winner raises `RepositoryConsistencyError`.

The losing transaction emits no duplicate event.

## Event

`analytics.interpreted` contains:

- analytics interpretation and snapshot IDs;
- mission, publication, and queue IDs;
- destination;
- ruleset version;
- overall classification;
- confidence;
- interpreted timestamp;
- actor; and
- payload hash.

It deliberately excludes the full interpretation payload.

## Command and HTTP boundaries

`MissionCommandService.interpret_analytics_snapshot` accepts only path-owned
mission and snapshot IDs plus the server-controlled actor. It does not accept
classifications, confidence, findings, source evidence, or summary.

The local dashboard endpoints are:

```text
GET  /missions/{mission_id}/analytics/{analytics_snapshot_id}/interpretation
POST /missions/{mission_id}/analytics/{analytics_snapshot_id}/interpret
```

The POST body is CSRF-only. It reuses the existing double-submit cookie,
constant-time comparison, local-host boundary, 12 KB body limit, strict form
model, repeated-field rejection, and safe exception mapping. Repository
details are returned only as a generic 503.

## Dashboard projection and UI

`DashboardAnalyticsInterpretation` projects typed durable records, latest and
historical interpretations, count, ruleset, classification, confidence,
findings, timestamp, source snapshot identity, availability, actionability,
and an explicit blocking reason.

Templates display persisted state and do not calculate classifications or
confidence. The analytics import history links each source snapshot to its
interpretation page. Interpretation creation remains an explicit separate
founder action.

## Test coverage

Focused tests cover frozen models, unknown fields, evidence states, zero and
missing inputs, deterministic output and explanations, Decimal hashing,
rounding, conservative classification/confidence, traceable findings,
repository parity, schema compatibility, exception translation, source
immutability, service validation, idempotency, events, collision recovery,
command authority, CSRF and form safety, safe HTTP mappings, GET rendering,
and typed dashboard projection.

Milestone 1 analytics import, publication confirmation, Mission Control,
commands, routes, dashboard projections, and the complete suite are regression
tested.

## Known limitations

- Version 1 has no platform- or niche-specific baselines.
- Only CTR and a strict engagement ratio are classified.
- Raw totals are intentionally not judged.
- There is no historical trend or cross-publication comparison.
- Manual source analytics are not independently verified.
- Interpretation does not yet feed mission learning; that requires a separate
  founder-approved milestone.
