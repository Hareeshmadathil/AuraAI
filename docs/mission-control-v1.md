# Mission Control V1

Mission Control is AuraAI's authoritative, founder-controlled coordination
kernel. It is additive: existing `mission_engine`, `runtime_engine`, department
pipelines, and dashboard contracts remain available as legacy execution and
projection APIs.

## Authority

`mission_control.MissionRecord` is the authoritative mission identity and
lifecycle. Existing mission objects may be adapted into it while preserving
their UUID. Mission Control owns canonical tasks, artifacts, approvals, and an
append-only event sequence.

## Architecture

```text
Founder policy
  -> MissionControlService
      -> MissionControlRepository
          -> SQLite (durable) or memory (tests)
      -> dependency-aware next-action calculation
      -> hash-bound ApprovalRequest
      -> typed DepartmentCommand / DepartmentResult
      -> read-only MissionControlProjection
```

The scheduler is pull-based and deterministic. It starts no background loop.
Department handlers are injected into `DepartmentBus`; Mission Control never
imports or directly couples departments.

## Persistence

Schema version 1 contains `missions`, `tasks`, `artifacts`, `approvals`, and
append-only `events`. Foreign keys are enabled. All values are bound query
parameters. The database path must resolve beneath its configured root. Schema
initialization is non-destructive and unknown versions are rejected.

## Lifecycle

```text
CREATED -> READY -> RUNNING
                    |-> APPROVAL_REQUIRED -> RUNNING
                    |-> BLOCKED -> READY
                    |-> PAUSED -> READY
                    |-> COMPLETED | FAILED | CANCELLED
```

Terminal states cannot transition. Pause, resume, cancellation, failure,
blocking, and approval waiting are explicit persisted states.

## Approvals

Consequential tasks are not schedulable without an approved, unexpired request
matching mission, task, requested action, and SHA-256 content hash. Rejected,
expired, revoked, or scope-mismatched requests grant no authority. Approval is
authorization only; Mission Control contains no provider, crawl, render,
distribution, or publishing implementation.

## Recovery and idempotency

On restart, interrupted ordinary tasks move to `RETRY_PENDING`; consequential
tasks move to `APPROVAL_REQUIRED`. They are never silently dispatched.
Idempotency keys are part of every task and command, completed results are
idempotent, and bounded attempts prevent unlimited retries.

## Dashboard

`MissionControlProjection` exposes missions, pending approvals, blocked tasks,
recent ordered events, artifacts, and health as typed read models. V1 does not
add mutable dashboard actions.

## Migration strategy

Existing public APIs are not removed. `mission_control.compatibility` adapts
legacy Mission Engine identities into authoritative records. Additional
runtime and dashboard adapters can be introduced incrementally; legacy models
must be labelled as projections rather than competing authorities.

## Safety boundaries

Mission Control performs no network access, browser launch, provider request,
rendering, upload, publishing, account operation, messaging, or purchase.
Consequential operations require separately injected adapters and a valid
founder approval gateway check.
