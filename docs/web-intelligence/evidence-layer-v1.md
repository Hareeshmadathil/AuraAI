# Evidence Layer V1

The Evidence Layer is the canonical boundary between public-source extraction
and AuraAI mission reasoning. It composes existing Web Intelligence,
Intelligence Director, and citation contracts; it does not introduce another
knowledge or intelligence system.

## Contract

`EvidenceDraft` is the provider-neutral adapter input. Deterministic fixtures
produce drafts today. A future approved Crawl4AI adapter may produce the same
contract without changing Mission Generator, Intelligence Director, Knowledge
Manager, or Mission Control.

`CanonicalEvidence` preserves:

- public source and bounded excerpt;
- source-authority assessment;
- observation and access timestamps;
- confidence, topic, and entities;
- freshness assessment and decay;
- preserved contradiction groups;
- adapter or fixture provenance;
- deterministic SHA-256 content hash;
- citation bound to the evidence identity;
- transparent rank score.

## Processing

```text
EvidenceDraft fixtures
  -> normalized SHA-256 identity
  -> exact duplicate removal
  -> source authority
  -> freshness policy
  -> contradiction classification
  -> citation binding
  -> evidence ranking
  -> existing TrendCandidate projection
  -> existing Mission Generator flow
```

Ranking weights authority at 50 percent, source confidence at 30 percent, and
freshness at 20 percent. Material or version contradictions subtract 35 points;
other contradictions subtract 10 points each. Scores are bounded to 0–100 and
ties use content hash ordering.

## Safety

V1 performs no network access, crawl, browser launch, provider request, render,
upload, or publish. Public URLs in fixtures are citation identifiers only. The
mission remains offline and stops at the existing founder approval boundary.
