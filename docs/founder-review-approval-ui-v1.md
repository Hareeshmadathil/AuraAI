# Founder Review & Approval UI V1

The founder review page is part of the existing FastAPI dashboard. It reads a
selected mission, tasks, artifacts, events, and approval request directly from
the injected Mission Control repository. The browser does not reconstruct or
grant approval authority.

Mutation requests are local-host-only, POST-only, form encoded, bounded, CSRF
protected, and strictly validated. Mission Control verifies the approval ID,
mission ID, task ID, requested action, exact SHA-256 content hash, pending
state, and expiry before recording a decision. Revision requests preserve all
existing mission artifacts and move the mission into its existing blocked,
recoverable state.

This V1 intentionally uses local machine access plus a CSRF-bound form as the
founder-presence boundary. It is not multi-user authentication and should not
be exposed on a network. Approval authorizes only the scoped offline content
request. It does not authorize providers, browsing, rendering, uploads,
publishing, spending, or any other downstream operation.
