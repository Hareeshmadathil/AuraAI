# Phase 1 — Application Composition Lifecycle

The normal application is composed explicitly by
`create_runtime_application_services`. One call creates one company roster,
employee registry, SQLite repository, Mission Control service, employee
dispatcher, mission runtime manager, and dashboard service.

```text
create_runtime_app
  -> create_runtime_application_services
      -> SQLiteMissionControlRepository (one connection)
      -> MissionControlService (one authority)
      -> MissionRuntimeManager (same authority)
      -> DashboardService (same authority)
  -> create_app
      -> FastAPI state (same services)
      -> dashboard and Mission Control routes
```

`create_app` remains an injection-friendly public factory. The normal
`create_runtime_app` factory selects the free SQLite backend at
`data/database/mission-control.db` unless an allowed test or deployment path is
provided.

The exported `app` object is a lazy ASGI compatibility wrapper. Importing
`app.main` does not open SQLite or construct runtime services; the normal
application is created once when the ASGI server first uses it.

The legacy `RuntimeOrchestrator` and `RuntimeStateManager` remain available for
compatibility and read projections. They are not constructed as mission
authorities by the normal composition root.

## Mission dashboard reads

The normal `DashboardService` owns no mission collection. On every snapshot it
uses `MissionControlDashboardReader`, which calls read-only query methods on the
same application-scoped `MissionControlService`. A transition is therefore
visible on the next dashboard request without synchronization or copied state.

Normal composition no longer constructs `RuntimeStateManager`. Legacy callers
may still inject it into `create_runtime_dashboard_service` for employee,
workflow, provider, health, and other non-authoritative runtime projections.
When Mission Control is supplied to the legacy dashboard adapter, runtime
snapshot missions are explicitly ignored.

## Normal mission commands

Normal mission mutations enter through `MissionCommandService`, which is a
thin application adapter over the one composition-root `MissionRuntimeManager`.
Mission submission calls `MissionRuntimeManager.create_mission`, which delegates
to Mission Control. Run-next calls `MissionRuntimeManager.run_next`; Mission
Control validates lifecycle state and task eligibility before the shared
`EmployeeDispatcher` executes anything.

```text
POST /api/missions
  -> MissionCommandService -> MissionRuntimeManager -> MissionControlService

POST /api/missions/{mission_id}/run-next
  -> MissionCommandService -> MissionRuntimeManager
      -> MissionControl scheduling -> EmployeeDispatcher -> Mission Control result
```

The normal command adapter has no repository, employee, legacy orchestrator, or
state-manager dependency. Demo and empty application factories do not configure
mission commands. `RuntimeOrchestrator` remains importable for legacy workflows
but is absent from normal application state and command routing.
