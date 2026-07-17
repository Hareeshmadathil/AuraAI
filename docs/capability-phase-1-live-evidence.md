# Capability Phase 1 — Live Evidence

The existing `CanonicalEvidence` contract remains unchanged. Injected evidence
providers must return that contract, and the existing Evidence Layer continues
to own confidence, authority, freshness, citation, contradiction, provenance,
and SHA-256 normalization. A small injected registry selects providers through
feature flags. Offline deterministic evidence is the default and fallback.

The Crawl4AI adapter accepts only an explicitly injected canonical collector;
it does not import Crawl4AI, launch a browser, or perform external work itself.
