# Phase 4 Milestone 5 — Closed Learning Loop

## Architecture

Version 1 closes the founder-controlled learning loop:

```text
Accepted MissionRecommendation
        ↓ explicit founder POST
MissionControlService.create_mission_from_recommendation
        ↓ existing MissionControlService.create_mission
Ordinary CREATED MissionRecord
        ↓
Existing runtime behavior
        ↓
STOP
```

Nothing happens automatically when a recommendation is created or accepted.
Only the local founder route can request a successor. Mission Control remains
the authoritative validator and write boundary, and the existing canonical
mission model and creation method are reused.

## Validation and founder authority

Mission Control requires a valid actor, source mission, and accepted
recommendation. It loads and validates the persisted lesson, interpretation,
snapshot, publication, and publishing queue item. Every mission ID, source ID,
destination, queue relationship, and publication content identity must match.
The deterministic recommendation is re-derived from its lesson and its payload
hash and content are checked for drift.

Pending and rejected recommendations fail closed. Acceptance alone does not
create a mission, add tasks, transition a workflow, or execute any runtime
operation.

## Successor mission

The successor is a normal `MissionRecord` in `CREATED` state. It is submitted
through `MissionControlService.create_mission`, producing the existing
`mission.created` event. It has no special tasks or runtime rules. Its title,
objective, confidence, departments, criteria, and other safe offline fields
are deterministically derived from the accepted recommendation and source
mission. The source mission ID is recorded as a mission dependency.

Normal Mission Control and runtime rules apply after creation. This milestone
does not start or execute the new mission.

## Durable lineage

Schema version 6 adds the immutable
`RecommendationMissionLineage` record and
`recommendation_mission_lineage` table. It stores:

- successor mission ID;
- source recommendation ID;
- source lesson ID;
- source interpretation ID;
- source snapshot ID;
- source publication ID;
- source queue item ID;
- source mission ID;
- founder actor and UTC creation time.

`source_recommendation_id` is the primary key and
`successor_mission_id` is unique. This makes one accepted recommendation map to
exactly one successor while allowing navigation and audit in both directions.
Migration from schema versions 1–5 is non-destructive.

Repository additions:

- `save_recommendation_mission_lineage`
- `find_recommendation_mission_lineage`
- `find_successor_mission_lineage`

Expected uniqueness collisions become `DuplicateRecordError`; unrelated
SQLite integrity failures remain `RepositoryIntegrityError`.

## Idempotency and concurrency

Creation checks lineage before work and again inside the repository
transaction. Repeated requests return the persisted successor. Concurrent
requests serialize on the repository transaction, producing one mission,
lineage record, and closed-loop event. Cross-process uniqueness collisions
reload the winner. A lineage referencing a missing mission fails with
`RepositoryConsistencyError`.

Mission creation, lineage, the normal creation event, and the closed-loop event
are committed atomically.

## Event

`mission.created_from_recommendation` contains:

- new mission ID;
- recommendation ID;
- lesson ID;
- interpretation ID;
- snapshot ID;
- publication ID;
- source mission ID;
- actor;
- UTC timestamp.

The full recommendation and lineage payloads are not copied into the event.

## Dashboard and route

The recommendation view displays whether a successor exists. Only an accepted
recommendation without lineage shows the explicit
**Create Mission From Recommendation** form. Existing successors link to their
standard founder review page. The successor review page links back to the
source recommendation.

The mutation route is:

```text
POST /missions/{source_mission_id}/recommendations/{recommendation_id}/create-mission
```

It is local-only, POST-only, CSRF protected with constant-time comparison,
body-size limited, repeated-field protected, and extra-field rejecting. The
form accepts only CSRF; mission content cannot be submitted by the caller.
The actor is server controlled and domain/repository errors are safely mapped.

## Testing and limitations

Focused tests cover accepted, pending, and rejected states; complete lineage;
ordinary mission state; sequential and concurrent idempotency; compact events;
schema migration; commands; typed dashboard state; explicit POST behavior;
CSRF and local boundaries; bidirectional navigation; and absence of automatic
creation.

Milestones 1–4 and publication/runtime behavior remain regression covered.
There is no automatic mission creation, acceptance, execution, continuation,
publishing, rendering, provider or LLM call, external service, or runtime
special case. The founder must separately operate the new mission through the
existing Mission Control lifecycle.
