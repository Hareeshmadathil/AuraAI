# Capability Phase 4 — Publishing Preparation

The existing Distribution models and Mission Control approval gateway remain
the authority boundaries. `PublishingPreparationService` creates immutable
YouTube, Instagram, and TikTok plans, scheduling proposals, metadata, policy
checks, upload manifests, and manual retry plans. It exposes no upload method.

Every manifest declares a separate `approve_publishing_manifest` action bound
to its SHA-256 hash. Even a valid existing approval only verifies the record;
publishing remains disabled and requires a future explicitly authorized
integration milestone.
