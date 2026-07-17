# Dashboard Operations V2

Dashboard Operations V2 is a read-only projection inside the existing FastAPI
dashboard. It derives mission counts, task progress, pipeline stages, founder
attention, activity, system readiness, and capability summaries directly from
the injected Mission Control repository. It creates no secondary state.

Pipeline stage status is inferred from the canonical mission status, approval
requests, tasks, and artifact types. Capability details remain linked to the
existing Founder Review page. The only mutation route remains the existing
CSRF-protected Founder Review decision endpoint.

External capabilities are reported honestly: deterministic evidence and
business metrics are offline fallbacks, Crawl4AI is unavailable without an
injected collector, Provider Router is offline fallback, and publishing
execution is disabled.
