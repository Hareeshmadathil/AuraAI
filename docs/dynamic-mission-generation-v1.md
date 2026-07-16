# Dynamic Mission Generation V1

Dynamic Mission Generation converts a founder goal into one canonical Mission
Control mission using only existing AuraAI reasoning and memory boundaries.

## Flow

```text
Founder goal
  -> Aura CEO structural review
  -> Trend Hunter deterministic candidate ranking
  -> Intelligence Director priority scoring
  -> Knowledge Manager exact-title duplicate check
  -> Mission Generator deterministic selection
  -> Mission Control authoritative persistence
  -> existing offline Mission Zero execution
  -> pending founder approval
```

The generator is a reusable integration service, not a manager, department,
mission engine, scheduler, approval system, knowledge system, or intelligence
system. Mission Control remains the sole mission authority.

## Determinism and selection

The mission UUID is UUIDv5-derived from the normalized founder goal. Duplicate
candidate names are removed case-insensitively before ranking. Intelligence
Director scores every remaining Trend Hunter opportunity; Knowledge Manager
then removes exact prior mission topics. Final score is 60 percent Trend Hunter
opportunity score and 40 percent Intelligence Director priority score. Ties use
case-insensitive title ordering.

## Canonical mission fields

The existing `mission_control.MissionRecord` now carries founder goal, expected
outcome, business value, difficulty, execution estimate, required departments,
approvals, success/failure criteria, expected artifacts, dependencies, provider
requirements, confidence, reasoning, and mission score. Offline execution is
always true; publishing and rendering requirements are type-constrained false.
Defaults preserve compatibility with previously persisted V1 mission records.

## Dashboard and execution

The existing Mission Control API exposes founder goal, generated mission,
score, priority, status, and recent timeline events. The generated mission is
passed to the unchanged Mission Zero task graph after Mission Control has stored
it. No duplicate dashboard or execution path is created.

## Safety

Generation uses deterministic fixtures and injected local services. It performs
no browse, crawl, provider request, browser launch, render, upload, publish, or
account operation. The resulting mission always stops at the existing pending
founder approval boundary.
