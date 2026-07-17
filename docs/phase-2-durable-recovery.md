# Phase 2 — Durable Recovery and Controlled Resume

Phase 2 extends the Phase 1 authority chain without adding another scheduler,
runtime manager, repository, or employee execution path.

```text
MissionCommandService
  -> RecoveryGate
  -> MissionRuntimeManager
      -> RestartReconciler
      -> MissionControlService
          -> SQLite schema v2
      -> EmployeeDispatcher
```

## Persistent state

SQLite schema version 2 retains all version 1 JSON records and adds `attempts`
and `checkpoints`. Opening a version 1 database creates the additive tables and
updates the schema marker in one local migration. Unknown schema versions fail.

An execution attempt is written before employee execution. It records identity,
mission/task/employee correlation, attempt number, starting task state,
timestamps, terminal status, failure classification, retry eligibility,
checkpoint/result references, and causation/correlation IDs. Completed attempt
records are never reopened. A started attempt remaining after process exit is
classified as interrupted during reconciliation.

A checkpoint belongs to one mission, task, attempt, and employee. Its sequence,
kind, JSON payload or artifact reference, SHA-256 checksum, resumability,
schema version, and creation time are durable. Checkpoints never complete tasks
and are accessed through the replaceable `CheckpointWriter` contract backed by
Mission Control.

## Startup reconciliation and gate

Normal composition creates exactly one `RecoveryGate`, injects it into the
shared runtime manager, and reconciles before mission commands become usable.
The gate states are `not_started`, `reconciling`, `ready`, `blocked`, and
`failed`. Read APIs remain available in every state. Mutation and execution
commands require `ready`, except the explicit recovery command and existing
founder-decision boundary.

Reconciliation scans every non-terminal mission without dispatching work. It
classifies findings as clean, interrupted, recoverable, retryable,
awaiting-founder, dependency-blocked, inconsistent, or requiring manual
intervention. Interrupted attempts become `interrupted`; interrupted tasks
become retry-pending, approval-required, or failed according to their bounded
policy. No result is fabricated and no approval is granted. Every report and
mutation is event-audited and safe to rerun.

## Retry policy

Retries are explicit and bounded by `maximum_attempts`. A task records retry
mode, backoff multiplier, deterministic `next_eligible_at`, and last failure
classification. Retry requires a running mission, satisfied dependencies, a
retry-pending task, elapsed delay, remaining attempts, a ready recovery gate,
and no pending founder approval. Each retry creates a new durable attempt;
there is no background retry loop.

Non-retryable failures block. Exhausted failures fail. Manual-only and never
policies cannot use the normal retry command.

## Controlled resume

Startup never resumes work. Resume is an explicit command through the normal
authority chain. When a checkpoint is supplied, Mission Runtime validates its
mission/task/attempt ownership, schema version, checksum, and resumability,
then applies the same current lifecycle, dependency, retry, approval, and gate
checks as a restart-from-beginning retry. A continuation always creates a new
attempt. Without a checkpoint, explicit resume follows the task's restart retry
policy; otherwise it is rejected.

## Founder approval

Approval-required missions and tasks remain paused across restart. Run-next,
retry, and resume reject unresolved approvals, and checkpoints cannot bypass
them. Only the existing founder-decision route can decide an approval.
Approval records and events retain approver, decision, timestamp, reason,
content hash, optional checkpoint binding, and causation/correlation IDs.
Changed content does not satisfy an approval bound to an older hash.

## Commands and visibility

- `POST /api/missions/{mission_id}/recover`
- `POST /api/missions/{mission_id}/tasks/{task_id}/retry`
- `POST /api/missions/{mission_id}/tasks/{task_id}/resume`
- `GET /api/recovery`

The dashboard snapshot and recovery API expose gate/report state, interrupted
tasks, attempt counts, last failure classification, retry eligibility and
exhaustion, checkpoint/resume availability, founder-review requirements, and
recommended safe actions. These projections use Mission Control queries and
perform no writes.

## Limitations and Phase 3 entry

Phase 2 does not provide a background scheduler, distributed locking, external
workers, or real rendering checkpoints. Execution remains local and explicitly
commanded. Phase 3 should first introduce a rendering task adapter that emits
the existing checkpoint contract while preserving founder approval before any
publishing preparation.
