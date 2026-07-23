# Phase 4 Milestone 3 — Mission Lessons Foundation

## Purpose and scope

Mission Lessons Foundation converts one persisted
`AnalyticsInterpretation` into one durable, deterministic `MissionLesson`.
The boundary is deliberately narrow:

```text
AnalyticsInterpretation
        ↓
MissionLesson
        ↓
STOP
```

A lesson records what the evidence established. It does not recommend an
action, create or advance a mission, change strategy, invoke a provider, or
perform an external operation.

## Architecture

`mission_control/mission_lessons.py` is a pure rules engine. It consumes an
immutable interpretation plus a supported ruleset and returns a canonical
payload. It has no database, clock, event, HTTP, provider, or LLM dependency.

`MissionControlService.create_mission_lesson` is the authoritative write
boundary. It loads the interpretation and its durable identity chain,
revalidates the interpretation against the source snapshot, invokes the pure
engine, assigns identity, actor, and UTC creation time, and atomically stores
the lesson and event.

Repository implementations own persistence and exception translation.
`MissionCommandService` delegates identities to Mission Control. Dashboard
routes accept no caller-derived lesson content, and templates display typed
persisted projections only.

## Domain model

The frozen, extra-field-rejecting domain types are:

- `MissionLesson`: durable identity, provenance, hash, confidence, summary,
  findings, strengths, weaknesses, unknowns, and evidence references.
- `LessonFinding`: one evidence-backed statement with its category,
  confidence, source classification, evidence state, rules, and references.
- `LessonEvidenceReference`: interpretation ID, snapshot ID, source metrics,
  classification, evidence state, and interpretation rule ID.
- `LessonCategory`: `performance_strength`, `performance_weakness`,
  `evidence_gap`, `insufficient_evidence`, and `observation`.
- `LessonConfidence`: `low`, `medium`, and `high`.
- `LessonEvidenceState`: `available`, `zero`, `missing`, and
  `not_applicable`.

UUIDs connect every lesson to its mission, publication, queue item, snapshot,
and interpretation. `created_at` must be timezone-aware UTC.

## Deterministic rules

Ruleset `mission-lesson-v1` preserves the authoritative interpretation:

- `strong` and `outstanding` metric classifications become strengths.
- `weak` metric classifications become weaknesses.
- missing and not-applicable evidence become evidence-gap unknowns.
- an overall `insufficient_data` result adds a conservative
  insufficient-evidence unknown.
- zero remains a distinct evidence state and is never treated as missing.
- average or otherwise unsupported conclusions do not produce findings.

The rules do not recalculate ratios or inspect raw analytics values. Ordering
follows the interpretation's stable metric ordering. Summary text is a fixed
template containing deterministic strength, weakness, and unknown counts.
Confidence is inherited from `InterpretationConfidence`; no probability is
invented.

Every finding includes its source metrics, classification, evidence state,
rule IDs, interpretation ID, snapshot ID, and evidence references. The
complete analytics snapshot is not copied into the lesson.

## Payload hash

The SHA-256 payload hash covers canonical JSON containing:

- interpretation ID and interpretation payload hash;
- lesson ruleset version;
- confidence and summary;
- findings, strengths, weaknesses, and unknowns;
- evidence references.

JSON keys are sorted and compactly encoded. Actor, creation time, and generated
lesson record ID are excluded, so equivalent inputs produce the same content
hash and ordinary retries remain idempotent.

## Persistence and migration

SQLite schema version is `4`. The non-destructive migration creates
`mission_lessons` and an ordered publication-history index while preserving
all earlier missions, queue items, publications, analytics snapshots,
interpretations, and events.

The table stores indexed identity fields plus the canonical serialized model.
Its durable uniqueness identity is:

```text
UNIQUE(analytics_interpretation_id, lesson_ruleset_version)
```

History is ordered by `created_at DESC, id DESC`. The in-memory repository
uses defensive model copies. Expected uniqueness collisions become
`DuplicateRecordError`; other SQLite integrity failures become
`RepositoryIntegrityError`. SQLite exceptions never enter the service.

Repository contract additions are:

- `save_mission_lesson`
- `find_mission_lesson_by_id`
- `find_interpretation_ruleset_lesson`
- `list_mission_lessons`

## Validation, idempotency, and concurrency

Mission Control validates the actor and ruleset; the mission,
interpretation, snapshot, publication, and queue item existence; mission
ownership; queue, publication, snapshot, and interpretation identities;
destination consistency; publication content identity; and the stored
interpretation payload hash re-derived from its durable snapshot.

An existing identity with the same payload hash is returned unchanged. A
different hash fails closed. First creation stores the lesson and appends
`analytics.lesson_created` in one transaction. If a concurrent writer wins,
Mission Control reloads and returns an identical winner, rejects a conflicting
winner, or raises `RepositoryConsistencyError` when no winner exists. Collision
recovery emits no second event.

The compact event contains lesson, interpretation, snapshot, mission,
publication, and queue IDs; destination; ruleset; confidence; creation time;
actor; and payload hash.

Source missions, workflow state, queue items, publications, snapshots, and
interpretations are never mutated.

## Command, routes, and dashboard

`MissionCommandService.create_mission_lesson` accepts only mission ID,
interpretation ID, and the server-controlled actor. It delegates all authority
to Mission Control.

The existing local dashboard exposes:

- `GET /missions/{mission_id}/analytics/interpretations/{analytics_interpretation_id}/lesson`
- `POST /missions/{mission_id}/analytics/interpretations/{analytics_interpretation_id}/lesson`

The POST is local-only, CSRF protected with constant-time comparison, form-size
limited, repeated-field protected, unknown-field rejecting, and accepts only
the CSRF token. Errors are mapped without leaking repository details. The
interpretation page links to lesson review, but interpretation and lesson
creation remain separate founder actions.

`DashboardMissionLesson` projects the latest durable lesson, deterministic
history, count, ruleset, confidence, summary, findings, evidence references,
strengths, weaknesses, unknowns, source identities, eligibility, and blocking
reason. Eligibility only controls whether the founder may request creation.

## Tests and limitations

Focused coverage verifies immutable typed models, deterministic generation and
hashing, evidence-state preservation, non-prescriptive language, repository
contracts and uniqueness, schema migration, service identity validation,
idempotency, event atomicity, concurrency recovery, command delegation, local
CSRF routes, safe errors, templates, and typed dashboard projections.

This milestone intentionally has no historical comparison, cross-publication
analysis, recommendation engine, learning automation, mission influence,
mission creation, workflow progression, provider use, or external execution.
Those remain future founder-controlled milestones.
