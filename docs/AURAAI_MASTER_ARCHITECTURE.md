# AuraAI Master Architecture and Product Constitution

**Status:** Authoritative project direction  
**Project:** AuraAI  
**Founder:** Hareesh Madathil  
**Purpose:** Define AuraAI's long-term vision, architectural boundaries, execution model, product roadmap, and engineering rules.

---

## 1. Executive Vision

AuraAI is not a chatbot and not a collection of disconnected AI agents.

AuraAI is a founder-controlled autonomous company operating system. It organizes AI executives, directors, specialists, workflows, durable mission state, production tools, publishing operations, analytics, financial controls, and founder approvals into one coherent system.

The long-term goal is for AuraAI to:

1. Discover and validate business opportunities.
2. Convert opportunities into structured missions.
3. Assign work to specialized AI employees.
4. Research, plan, produce, render, package, and publish assets.
5. Pause whenever founder approval is required.
6. Recover safely after interruption or restart.
7. Import real performance and financial data.
8. Learn from results.
9. Recommend the next best mission.
10. Generate sustainable revenue through multiple controlled business lines.

AuraAI must become increasingly capable without becoming uncontrolled, opaque, fragile, or dependent on one provider.

---

## 2. Founder Authority

The founder is the highest authority in AuraAI.

No AI executive, director, specialist, runtime component, provider, automation, or external service may override founder authority.

The founder must retain the ability to:

- create, approve, reject, pause, resume, or cancel missions;
- approve content before publishing;
- confirm manual publication;
- inspect mission history and artifacts;
- inspect decisions and employee outputs;
- override recommendations;
- disable providers or employees;
- control budgets and spending;
- control credentials and platform access;
- review analytics and lessons;
- decide when AuraAI may move from simulation to real-world execution.

High-impact actions must require explicit founder approval unless the founder has created a specific, limited policy authorizing them.

---

## 3. Product Identity

AuraAI should feel like a real operating system for an AI company.

The dashboard should eventually provide:

- company overview;
- executive and employee roster;
- active missions;
- mission timelines;
- approvals requiring founder attention;
- workflows and execution attempts;
- production artifacts;
- rendering progress;
- publishing queue;
- publication confirmations;
- analytics;
- lessons learned;
- provider health;
- budget and financial status;
- audit logs;
- system recovery state.

The system should be understandable to a founder who is not a software engineer. Internal architecture may be sophisticated, but the founder experience must remain clear.

---

## 4. Core Design Checklist

Every major design decision must be evaluated against these five questions:

1. Does it improve output quality?
2. Can it scale without creating architectural confusion?
3. Will it remain maintainable?
4. Can the component be replaced without rewriting the whole system?
5. Does it contribute directly or indirectly toward generating sustainable revenue?

A feature that fails these questions should be postponed, simplified, or rejected.

---

## 5. Cost Strategy

Until AuraAI generates reliable income:

- prefer free and open-source tools;
- prefer local or low-cost deterministic execution;
- avoid unnecessary subscriptions;
- avoid expensive infrastructure;
- avoid premature enterprise services;
- use paid tools only when they clearly improve revenue, reliability, or quality enough to justify the cost;
- preserve provider abstraction so free tools can later be replaced by paid services without redesigning the system.

AuraAI must never spend money autonomously without an explicit founder-approved budget and policy.

---

## 6. Company Structure

### 6.1 Founder

The founder defines company direction, approves sensitive actions, and owns final business authority.

### 6.2 Executive Layer

- **CEO:** Converts founder intent into company priorities and mission proposals.
- **COO:** Coordinates operations, sequencing, dependencies, and execution readiness.
- **CTO:** Owns technology strategy, architecture recommendations, provider strategy, and engineering quality.
- **CFO:** Owns budgeting, cost controls, profitability analysis, and financial risk.

Executives advise and coordinate. They do not bypass Mission Control or directly mutate durable state.

### 6.3 Director Layer

Planned directors include:

- Research Director
- Marketing Director
- Production Director
- Publishing Director
- Analytics Director
- Finance Director
- Engineering Director
- Operations Director

Directors decompose approved goals into department work and supervise specialists through typed tasks and results.

### 6.4 Specialist Layer

Planned specialists include:

- Research Analyst
- Trend Hunter
- Niche Validation Specialist
- Competitor Analyst
- SEO Specialist
- Script Writer
- Copywriter
- Voice Artist
- Thumbnail Designer
- Video Editor
- Shorts Editor
- YouTube Manager
- Instagram Manager
- TikTok Manager
- Analytics Specialist
- Financial Analyst
- Quality Reviewer

Each specialist should have one clear responsibility and a replaceable implementation.

---

## 7. Authoritative Runtime Architecture

AuraAI must maintain one authoritative execution path.

### 7.1 Permanent Authorities

- **MissionControlService:** Sole durable mission-state and persistence authority.
- **MissionRuntimeManager:** Sole normal mission-execution orchestrator.
- **EmployeeDispatcher:** Sole employee resolution and dispatch boundary.
- **Application Composition:** Sole construction point for runtime dependencies.
- **MissionCommandService:** Founder/application command boundary.

### 7.2 Canonical Call Direction

Founder or application command  
→ MissionCommandService  
→ MissionRuntimeManager  
→ MissionControlService  
→ EmployeeDispatcher  
→ Employee  
→ DepartmentResult  
→ MissionControlService  
→ Dashboard projection

Recovery components may reconcile interrupted state during startup, but they must not become a second normal execution path.

### 7.3 Forbidden Parallel Authorities

Never introduce:

- a second Runtime Manager;
- a second Mission Control;
- a second employee dispatcher;
- a second mission state machine;
- a second normal execution runner;
- a duplicate repository for the same domain;
- a duplicate approval framework;
- a duplicate publishing queue;
- a duplicate rendering pipeline;
- direct dashboard writes to mission state;
- employee access to SQLite;
- provider-specific logic inside canonical domain models.

Extend existing authority instead of creating competing systems.

---

## 8. Persistence and Durable State

SQLite is the current durable persistence layer because it is suitable for the present scale and cost strategy.

All important mission operations must survive process restart.

Durable records should include, where applicable:

- missions;
- mission state;
- tasks;
- decisions;
- approvals;
- execution attempts;
- retries;
- checkpoints;
- render jobs;
- artifacts;
- publishing queue items;
- publication confirmations;
- analytics imports;
- lessons;
- recommendations;
- financial events;
- audit history.

Persistence implementation must remain behind repository and service boundaries so SQLite can later be replaced without changing the whole application.

---

## 9. Mission Execution Principles

Every mission must be:

- durable;
- observable;
- resumable;
- idempotent;
- auditable;
- founder-controllable;
- bounded by retry policy;
- protected from duplicated execution;
- expressed through typed, serializable contracts.

Employees do not own mission state. They perform assigned work and return structured results.

Commands and task payloads must contain serializable domain data only. Python services, repositories, database connections, provider clients, and adapters must be injected through application composition, never stored in durable payloads.

---

## 10. Mission Lifecycle

The exact enum names must follow the existing repository. The conceptual lifecycle is:

1. Mission created.
2. Mission validated and accepted.
3. Research.
4. Strategy.
5. Content planning.
6. Production.
7. Founder content review.
8. Rendering.
9. Publishing preparation.
10. Founder publishing approval.
11. Ready for manual publishing.
12. Awaiting manual publication confirmation.
13. Publication confirmed.
14. Analytics collection.
15. Lesson extraction.
16. Next-mission recommendation.
17. Completed or archived.

Critical distinction:

**Publishing approval** authorizes the prepared package to be published.

**Manual publication confirmation** records that the founder or authorized operator actually published it.

AuraAI must never mark an item as published merely because it is ready.

---

## 11. Approval Model

Founder approval must be durable and explicit.

Separate approval types should exist for separate decisions, including:

- mission approval;
- strategy approval;
- content approval;
- rendering approval where needed;
- publishing approval;
- budget approval;
- manual publication confirmation.

Approvals should contain:

- approval type;
- mission identifier;
- related task, artifact, render job, or queue item;
- requested time;
- decision time;
- decision;
- founder comment;
- version or integrity reference;
- audit metadata.

Approval of one artifact version must not silently approve a later modified version.

---

## 12. Checkpoints and Recovery

Checkpoints represent completed execution boundaries.

A checkpoint should contain enough information to prove what was completed and safely resume without repeating expensive or unsafe work.

Checkpoint requirements:

- associated mission;
- associated task;
- associated canonical attempt;
- execution step;
- registered artifact IDs;
- integrity metadata;
- relevant render job or queue item metadata;
- creation time;
- deterministic recovery data.

Recovery may inspect earlier interrupted attempts, but newly written checkpoints must belong to the active canonical attempt.

For rendering, checkpoint reuse must be isolated by render job. A checkpoint belonging to a different render job must never be reused.

Artifacts must be resolved through the artifact registry and validated against approved roots and integrity hashes before recovery skips a step.

---

## 13. Artifact Management

Filesystem paths are not domain authority.

AuraAI should register artifacts and refer to them by durable artifact identifiers.

Artifact records should include:

- artifact ID;
- mission ID;
- task ID;
- artifact type;
- storage reference;
- content hash;
- size;
- media metadata where relevant;
- version;
- producer;
- creation time;
- status.

Only approved storage roots may be used. Path traversal and symlink escape must be rejected.

Artifacts must be replaceable and versioned. Derived assets should reference their source artifacts where practical.

---

## 14. Rendering Architecture

Rendering is performed by a specialized employee behind narrow interfaces.

The Render Specialist:

- performs rendering work only;
- receives dependencies through constructor injection;
- does not access MissionControlService directly;
- does not access repositories or SQLite;
- does not transition mission state;
- does not finish attempts;
- returns structured DepartmentResult data.

MissionRuntimeManager owns rendering orchestration within the canonical attempt lifecycle.

Rendering must support:

- deterministic preparation;
- narration generation;
- narration recovery;
- final rendering;
- checkpoint creation;
- cross-attempt recovery;
- artifact integrity verification;
- idempotent duplicate commands;
- render-job isolation.

---

## 15. Publishing Architecture

Publishing must initially remain founder-controlled and manual.

AuraAI should prepare complete publishing packages but should not directly publish to external platforms until the manual loop is proven reliable and the founder explicitly approves platform integration.

A publishing package may contain:

- final video or media artifact;
- thumbnail;
- title;
- description;
- captions;
- hashtags;
- tags;
- platform-specific copy;
- scheduled date recommendation;
- compliance notes;
- source artifact references;
- content version;
- package integrity data.

The durable publishing queue should support:

- one queue item per platform/package destination;
- deterministic creation;
- idempotency;
- restart recovery;
- approval state;
- readiness state;
- manual publish confirmation;
- external post URL or platform ID after confirmation;
- publication timestamp;
- failure and retry notes.

No queue item should become published without explicit publication confirmation.

---

## 16. Analytics and Learning

Analytics comes after the publishing loop works.

Initial analytics may be imported manually. Later, provider adapters may automate collection.

Analytics should normalize platform-specific data into a provider-neutral model, including:

- views;
- watch time;
- retention;
- clicks;
- impressions;
- engagement;
- followers or subscribers gained;
- conversions;
- leads;
- revenue;
- cost;
- profit where known.

The learning layer should:

- compare actual outcomes with mission assumptions;
- identify what worked and what failed;
- store evidence-backed lessons;
- avoid treating one result as universal truth;
- recommend the next mission;
- show uncertainty and supporting data;
- require founder approval before executing major new strategies.

---

## 17. Revenue Architecture

AuraAI should support multiple future revenue models, but only after the operational loop is reliable.

Potential revenue paths include:

- content-driven affiliate businesses;
- lead generation;
- digital products;
- content services;
- research reports;
- niche media brands;
- e-commerce support;
- automation services;
- advertising revenue;
- subscription products.

Each business mission should define:

- target customer;
- problem;
- offer;
- channel;
- cost;
- expected revenue;
- validation criteria;
- success metrics;
- stop conditions;
- founder-approved risk limit.

AuraAI must not pretend revenue exists. Revenue must be imported from verifiable records or confirmed by the founder.

---

## 18. Finance and Budget Controls

The future CFO and Finance Department should provide:

- mission budgets;
- provider-cost tracking;
- cost per artifact;
- cost per published item;
- revenue attribution;
- profitability estimates;
- cash-flow visibility;
- budget warnings;
- spending approval requests.

No employee may purchase services or spend funds unless the founder has approved a bounded policy.

Financial data should be auditable and separated from speculative forecasts.

---

## 19. Provider Strategy

AuraAI must remain provider-neutral.

Examples of replaceable providers include:

- language models;
- web research;
- search;
- voice synthesis;
- transcription;
- image generation;
- video rendering;
- storage;
- publishing;
- analytics;
- payments.

Canonical domain models must not depend on Gemini, OpenAI, FFmpeg, YouTube, Instagram, TikTok, Shopify, or any other individual provider.

Provider adapters should implement narrow interfaces and expose capability and health information.

A provider failure should not corrupt mission state.

---

## 20. Web Intelligence

Live web intelligence should be added only after the core mission loop is complete.

It should support:

- source attribution;
- freshness;
- confidence;
- deduplication;
- evidence storage;
- provider abstraction;
- legal and policy compliance;
- safe handling of unavailable or contradictory sources.

Research outputs should distinguish facts, estimates, opinions, and assumptions.

---

## 21. Dashboard Principles

The dashboard is a projection and control surface, not an independent authority.

The dashboard may:

- display state from Mission Control;
- send explicit commands;
- show approvals;
- show recovery status;
- show artifacts;
- show queue items;
- show analytics and lessons.

The dashboard must not:

- directly mutate repositories;
- invent mission state;
- bypass MissionCommandService;
- perform hidden execution;
- mark publication complete without confirmation.

Every founder-facing action should explain what will happen before it executes.

---

## 22. Security and Safety

AuraAI must apply least privilege.

Requirements include:

- secrets stored outside source control;
- credentials never written into mission payloads;
- external integrations isolated behind adapters;
- approved path roots;
- artifact hash verification;
- sanitized filenames and URLs;
- bounded retries;
- timeout controls;
- audit logging;
- safe cancellation;
- approval before irreversible actions;
- no autonomous financial spending;
- no autonomous publication until explicitly authorized.

---

## 23. Testing Standard

Every milestone requires:

1. Focused tests for new behavior.
2. Regression tests for previously completed behavior.
3. Full-suite execution.
4. Clean test completion with no hidden teardown errors.
5. Exact test totals reported.
6. Architecture-boundary tests where relevant.
7. Idempotency tests.
8. restart/recovery tests where relevant.
9. failure-path tests.
10. no commit until founder review.

Tests should be deterministic and offline where practical.

Warnings must be reported. Known dependency warnings may be accepted temporarily but should be tracked.

---

## 24. Development Workflow

AuraAI uses review-driven development.

For every milestone:

1. Inspect the repository.
2. Present an implementation plan.
3. Identify exact files and symbols.
4. Confirm architectural boundaries.
5. Receive founder approval.
6. Implement only the approved scope.
7. Run focused tests.
8. Run the full suite.
9. Present modified-file list and walkthrough.
10. Stop for review.
11. Commit, tag, and push only after approval.

The implementation agent must not silently continue into the next milestone.

---

## 25. Documentation Standard

Documentation must match the actual source code.

Required documents should include:

- master architecture;
- milestone implementation notes;
- state diagrams;
- recovery rules;
- provider contracts;
- founder operating manual;
- deployment and startup instructions;
- troubleshooting;
- migration notes.

Outdated documentation must be corrected when implementation changes.

---

## 26. Roadmap

### Phase 1 — Authoritative Runtime ✅

- one Runtime Manager;
- one Mission Control authority;
- one Employee Dispatcher;
- persistent mission state;
- dashboard projection.

### Phase 2 — Durable Recovery ✅

- restart reconciliation;
- durable execution attempts;
- checkpoints;
- bounded retry;
- resume;
- founder approval pauses;
- startup and command gating;
- recovery visibility.

### Phase 3 — Production and Manual Publishing Loop

#### Milestone 1 ✅
- RenderJob domain model;
- PublishingQueueItem domain model;
- durable repository foundations.

#### Milestone 2 ✅
- deterministic Render Specialist;
- checkpointed rendering;
- cross-attempt recovery;
- artifact integrity checks;
- render-job checkpoint isolation.

#### Milestone 3
- durable publishing package and queue creation;
- transition from rendering completion into publishing preparation;
- idempotent queue population;
- platform-neutral queue contracts;
- no external publishing.

#### Milestone 4
- founder publishing approval;
- ready-for-manual-publish state;
- dashboard queue and approval visibility;
- rejection and revision flow.

#### Milestone 5
- manual publication confirmation;
- record external URL or platform ID;
- published-confirmed state;
- restart-safe completion;
- first complete end-to-end mission.

### Phase 4 — Analytics and Learning Loop

- manual analytics import;
- normalized analytics model;
- lesson storage;
- evidence-backed mission review;
- next-mission recommendation;
- founder approval for follow-on missions.

### Phase 5 — Live Intelligence and Validation

- web research adapters;
- real niche validation;
- source evidence;
- competitor intelligence;
- trend monitoring;
- opportunity scoring.

### Phase 6 — Business and Finance

- CFO;
- Finance Department;
- budgets;
- costs;
- verified revenue;
- profitability;
- business portfolio;
- risk controls.

### Phase 7 — Controlled External Integrations

- YouTube adapter;
- Instagram adapter;
- TikTok adapter;
- commerce adapters;
- analytics adapters;
- optional automated scheduling;
- founder-defined publishing policies.

### Phase 8 — Multi-Business Operations

- multiple brands or companies;
- separate missions, budgets, assets, and analytics;
- portfolio-level prioritization;
- shared infrastructure without mixed state.

### Phase 9 — Self-Improvement Under Governance

- performance evaluation;
- provider comparison;
- prompt and workflow versioning;
- controlled experiments;
- evidence-based optimization;
- rollback;
- founder oversight.

---

## 27. Definition of the First Complete Operational Loop

AuraAI's first complete operational loop is achieved when it can:

1. create or accept a mission;
2. execute research and planning;
3. produce content;
4. pause for founder review;
5. render durable artifacts;
6. create a publishing package;
7. pause for publishing approval;
8. become ready for manual publishing;
9. wait for founder publication confirmation;
10. record publication evidence;
11. survive restart at every stage;
12. display the full lifecycle in the dashboard.

Only after this loop works should AuraAI prioritize live web intelligence, real analytics adapters, direct platform publishing, CFO automation, and multi-channel autonomous operations.

---

## 28. Non-Goals for the Current Stage

Do not prioritize:

- unrestricted autonomous behavior;
- direct social publishing;
- crypto wallets;
- autonomous purchasing;
- large cloud infrastructure;
- multi-tenant enterprise architecture;
- complex microservices;
- premature distributed queues;
- self-modifying production code;
- uncontrolled agent spawning;
- speculative finance features.

Robustness comes before feature volume.

---

## 29. Architecture Decision Rule

When a requested feature conflicts with this constitution:

1. preserve founder authority;
2. preserve the canonical runtime path;
3. preserve durable state and idempotency;
4. preserve replaceability;
5. choose the smallest safe implementation;
6. document the tradeoff;
7. request founder review before proceeding.

---

## 30. Final Direction

AuraAI should grow as a controlled, durable, understandable autonomous company system.

It must not become a fragile demonstration made from disconnected agents.

Every milestone should strengthen the same operating loop:

**Mission → Work → Artifact → Review → Publish → Measure → Learn → Recommend**

The founder remains in control while AuraAI steadily takes on more operational responsibility.
