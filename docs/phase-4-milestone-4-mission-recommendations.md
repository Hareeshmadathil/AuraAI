# Phase 4 Milestone 4 — Founder-Reviewed Mission Recommendations

## Purpose and boundary

This milestone converts one persisted `MissionLesson` into one durable,
deterministic, advisory `MissionRecommendation`, then stops at explicit founder
review:

```text
MissionLesson → MissionRecommendation → Founder review → STOP
```

Acceptance is a durable opinion for possible future use. It does not create or
progress a mission, transition a workflow, execute research, render, publish,
call a provider, or influence automated learning.

## Architecture

`mission_control/mission_recommendations.py` is a pure engine. It accepts an
immutable lesson and `mission-recommendation-v1`, and returns canonical
content without database, HTTP, clock, actor, provider, or LLM dependencies.

`MissionControlService` remains the only write authority. It validates and
re-derives the complete lesson-to-analytics identity chain before creation.
It assigns identity, actor, and UTC time and atomically stores the record and
event. Founder decisions use the same transaction boundary and never touch
mission execution state.

Repositories own persistence, locking, defensive copies, and SQLite exception
translation. Commands accept identities and founder review input only. Routes
do not generate proposals, and templates render persisted typed projections.

## Models and deterministic rules

Frozen, extra-field-rejecting models are `MissionRecommendation`,
`RecommendationProposal`, and `RecommendationEvidenceReference`. Typed enums
define categories, confidence, status, and decision.

Categories are preservation of a strength, addressing a weakness, collecting
more evidence, avoiding an unsupported conclusion, and no actionable
recommendation. Confidence is inherited from the lesson as low, medium, or
high; it is not probabilistic.

The v1 engine uses stable lesson-finding order:

- supported strengths produce cautious preservation proposals;
- supported weaknesses produce cautious future testing proposals;
- evidence gaps and insufficient evidence produce evidence-collection
  proposals;
- unsupported findings produce nothing;
- a lesson with no responsible proposal produces a deterministic no-actionable
  proposal.

Proposals claim neither causation nor guaranteed outcomes. Mixed evidence is
preserved. Raw analytics are not recalculated.

Evidence references include lesson ID, stable finding index, interpretation
and snapshot IDs, lesson category, source classification and evidence state,
lesson rule IDs, and recommendation rule ID. Complete source payloads are not
duplicated.

## Hash, identity, and persistence

Canonical compact sorted JSON is SHA-256 hashed. The content hash includes the
lesson ID and payload hash, recommendation ruleset, confidence, summary,
proposals, rationale, and evidence references. It excludes recommendation ID,
actor, creation time, status, decision metadata, and founder note.

Durable uniqueness is:

```text
UNIQUE(mission_lesson_id, recommendation_ruleset_version)
```

SQLite schema version is 5. Migration creates `mission_recommendations` and a
publication/time history index non-destructively from schema versions 1–4,
preserving all earlier records and events. History order is
`created_at DESC, id DESC`.

Expected identity collisions become `DuplicateRecordError`; other integrity
failures become `RepositoryIntegrityError`. SQLite exceptions do not enter the
service.

Repository additions:

- `save_mission_recommendation`
- `update_mission_recommendation`
- `find_mission_recommendation_by_id`
- `find_lesson_ruleset_recommendation`
- `list_mission_recommendations`

## Creation and founder review

`create_mission_recommendation` accepts mission ID, lesson ID, actor, and the
supported ruleset. It validates mission ownership and every lesson,
interpretation, snapshot, publication, queue, destination, and content
identity, then re-derives the authoritative lesson. Equivalent retries return
the existing record. Conflicting content fails closed. Concurrent duplicate
recovery returns an identical winner, rejects a conflict, or raises
`RepositoryConsistencyError` when no winner exists.

The lifecycle is:

```text
pending → accepted
pending → rejected
```

There is no executed, completed, reopened, or automatic state. Equivalent
normalized repeated decisions return the final record without another event.
Conflicting decisions, actors, or notes fail closed.

Creation emits `analytics.recommendation_created`. Review emits
`analytics.recommendation_reviewed`. Events are compact; review events include
only whether a reason exists, not its text. State and event writes are atomic
and retries do not duplicate events.

## Founder-controlled dashboard

The local-only routes are:

- `GET/POST /missions/{mission_id}/lessons/{mission_lesson_id}/recommendation`
- `POST /missions/{mission_id}/recommendations/{mission_recommendation_id}/{decision}`

Creation accepts only CSRF. Review accepts CSRF and an optional normalized
2,000-character founder note. Forms enforce content type, size, single values,
unknown-field rejection, constant-time CSRF comparison, server-controlled
actor, local access, and safe error mapping.

`DashboardMissionRecommendation` exposes persisted content, history, source
identities, status, review metadata, creation eligibility, review eligibility,
and blocking reason. Eligibility never triggers execution.

## Testing and limitations

Focused tests cover deterministic advisory generation, evidence traceability,
immutability, hashing, schema migration, repository identity, service
validation, source immutability, idempotency, collisions, final review
transitions, events, command boundaries, CSRF routes, templates, and typed
dashboard projections. Milestones 1–3 and publication behavior remain
regression-covered.

This milestone intentionally provides no mission creation, mission
progression, recommendation execution, cross-mission automation, external
operation, provider call, or automatic learning influence.
