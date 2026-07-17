# Phase 1 — Authoritative Runtime

`MissionRuntimeManager` is the replacement execution facade for new mission
work. It stores no mission, task, approval, artifact, or event state. All such
state belongs to the injected `MissionControlService` and its repository.

```text
MissionRuntimeManager
  -> MissionControlService (authority and scheduling)
      -> SQLiteMissionControlRepository (persistent state)
  -> EmployeeDispatcher (only employee execution boundary)
      -> EmployeeRegistry
      -> BaseEmployee
```

The manager asks Mission Control for the next dependency-ready action, obtains
the canonical command, sends it through the single dispatcher, and returns the
correlated result to Mission Control. It cannot skip dependencies or directly
mutate mission state.

SQLite is the default free persistence backend. Reconstructing the manager
with the same database restores the same canonical state. Interrupted-task
recovery is exposed through the manager but remains implemented by Mission
Control.

The legacy `RuntimeOrchestrator` and `RuntimeStateManager` remain available for
compatibility and dashboard projections. New mission execution must use
`MissionRuntimeManager`; later migration work will remove their authority over
missions.
