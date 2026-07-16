# Mission Zero Integration V1

Mission Zero Integration connects AuraAI's existing offline subsystems through
the authoritative Mission Control kernel. It introduces no new manager,
department, approval gateway, mission engine, scheduler, dashboard, or database.

## Execution path

```text
Founder goal
  -> Mission Control
  -> Aura CEO
  -> Orion COO
  -> Trend Hunter
  -> Intelligence Director
  -> Knowledge Manager
  -> Web Intelligence (OFFLINE)
  -> Research Department
  -> Production Research
  -> Provider Router (unavailable transports; no request)
  -> existing script-v2
  -> Production Connector status/package validation
  -> Private Video Production plan (export and render disabled)
  -> Creative Quality deterministic pipeline
  -> pending Mission Control founder approval
  -> STOP
```

Each stage is an existing subsystem handler registered with the existing typed
`DepartmentBus`. Mission Control calculates the only next action, dispatches a
typed command, accepts the typed result, registers its SHA-256-bound logical
artifact, and appends correlated events. Handlers do not invoke one another.

## Persistence and timeline

The existing Mission Control SQLite repository stores one canonical mission,
fourteen dependency-ordered tasks, thirteen stage artifacts, the append-only
event stream, and one pending approval request. The mission timeline is a
read-only replay of the authoritative event sequence; it is not duplicated in
a second table or scheduler.

## Dashboard

The existing `DashboardService` receives the Mission Engine compatibility
projection with the canonical Mission Control UUID. The existing
`/api/mission-control` endpoint exposes pending approvals, blocked tasks,
artifacts, and recent events. No dashboard mutation route is added.

## Safety boundary

Web Intelligence remains in `OFFLINE` mode. The Provider Router is composed
only with unavailable transports and no routing request is made. Private Video
Production runs `prepare(..., export=False)` without narration or rendering.
Production Connector performs validation and status projection only. The
mission stops before approval is granted and cannot render, upload, publish,
browse, or call an external provider.
