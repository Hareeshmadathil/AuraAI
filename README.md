# AURA AI

## Vision

AURA AI is an AI-powered content automation platform.

The goal is to transform one long-form video into multiple viral short-form videos automatically.

## Planned AI Agents

- Video Downloader
- Audio Extractor
- Speech-to-Text
- Content Analyzer
- Viral Clip Finder
- Video Editor
- Caption Generator
- Thumbnail Generator
- SEO Generator
- Publishing Agent

## Founder

Hareesh Madathil

## Local Dashboard

Install the open-source project dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the dashboard with deterministic local sample data:

```powershell
python -m uvicorn app.main:create_demo_app --factory --reload
```

Open `http://127.0.0.1:8000`. Demo mode is visibly labeled and does
not represent real production activity.

Run the safe empty-state dashboard instead:

```powershell
python -m uvicorn app.main:app --reload
```

Run the deterministic end-to-end niche discovery demonstration:

```powershell
python -m uvicorn app.main:create_niche_discovery_demo_app --factory --reload
```

This demonstration uses fixed sample candidates, does not perform live
market research, and clearly labels its dashboard state as sample data.

## Production Department v1

Run the deterministic content-production demonstration:

```powershell
python -m uvicorn app.main:create_content_production_demo_app --factory --reload
```

Open `http://127.0.0.1:8000/production` for the production package or
`http://127.0.0.1:8000/api/dashboard` for its JSON projection. The demo
creates a content brief, deterministic script, storyboard, voice and
visual plans, three thumbnail concepts, Shorts/Reels/TikTok derivatives,
in-memory subtitles, a non-rendered assembly manifest, and a quality
report. It stops at explicit founder approval.

Production v1 does not generate images, audio, music, or video; invoke
FFmpeg; upload content; or publish to a platform. All demo output is
labelled SAMPLE, PLANNED, and NOT RENDERED. Future generation and render
services must implement the injected contracts in `production/providers/`.

`ArtifactStore` writes nothing during import. When explicitly injected
and called, it can keep artifacts in memory or save UTF-8 JSON, text,
SRT, and VTT files beneath a configured root with traversal and overwrite
protection. Runtime output remains covered by the existing `outputs/`
ignore rule.

Only original, public-domain, or properly licensed assets should replace
the planned visual requests. Copyrighted characters, unauthorized logos,
living-artist imitation, unsupported claims, and revenue guarantees are
prohibited. Keep this unauthenticated server bound to a local interface;
automatic publishing is not available.

The dashboard currently uses injected in-memory state. It has no
database, authentication, live refresh, external platform connection,
or publishing capability. Do not expose this unauthenticated local
server to a public network.

## Production v2 local render pilot

Production v2 can turn the deterministic, quality-checked Production v1
package into a bounded set of local review artifacts. It detects locally
installed FFmpeg, FFprobe, and Windows speech support at run time. It does
not download assets, call external services, upload media, or publish.

Run the pilot only with explicit render approval:

```powershell
python -m production.rendering.pipeline --demo --founder-render-approved --output-root outputs/production
```

If local speech is unavailable, the render remains blocked unless the
operator explicitly adds `--silent-fallback`. That fallback is visibly and
structurally labelled as silent. Existing package directories are protected
unless `--overwrite` is supplied. Outputs include a review MP4, one vertical
short, a PNG thumbnail, WAV narration, UTF-8 SRT/VTT sidecars, a JSON render
manifest, and SHA-256 metadata beneath the ignored `outputs/production/`
directory. Intermediate scene clips are removed after successful assembly
unless `--keep-intermediates` is supplied.

All artifacts are marked sample data, review-required, and not published.
The `/renders` dashboard route displays only explicitly injected artifact
metadata. `/artifacts/{artifact_id}` accepts a registered UUID rather than a
filesystem path and refuses files outside the configured output root.

## Intelligence Department v1

The deterministic Intelligence stage sits between Research and Production.
It coordinates Trend Analyst, Competitor Analyst, Audience Analyst, SEO
Director, Retention Engineer, and Thumbnail Analyst employees through the
existing `BaseEmployee` task lifecycle and Runtime Engine.

Run its local dashboard demonstration with:

```powershell
python -m uvicorn app.main:create_intelligence_demo_app --factory --reload
```

Open `http://127.0.0.1:8000/intelligence`. The page shows the typed trend,
competitor, audience, SEO, hook, and thumbnail reports. All analysis comes
from an injected deterministic provider. It does not perform live research,
call platform APIs, require credentials, or guarantee reach or retention.

When the standard content-production mission receives a niche-discovery
result, the factory-backed flow is now Research → Intelligence → Production.
Direct `ProductionInput` and prebuilt `IntelligencePackage` inputs remain
supported. Rendering remains an explicit, separately approved local step.

## Content Quality Engine v1

AuraAI now includes an offline Creative Quality stage between Production and
founder-approved local rendering. Muse, the Creative Quality Director,
coordinates Hook Architect, Story Director, Retention Auditor, Motion
Designer, Subtitle Designer, Thumbnail Psychologist, and Factuality Reviewer
employees through the standard `BaseEmployee` lifecycle.

The engine scores hook, story, pacing, retention, clarity, motion, subtitles,
thumbnail, factuality, trust, call to action, and production completeness with
documented weights. These values are internal deterministic heuristics. They
do not predict real views, retention, click-through rate, subscribers, or
revenue.

The quality gate passes only when its configurable threshold is met and no
blockers exist. Low-risk subjective variance may require an explicit founder
override; factuality, trust, safety, copyright, and security blockers cannot
be overridden. A bounded revision engine updates a copied package without
fabricating facts, removing evidence warnings, or mutating the original.
Quality approval never grants render or publishing approval.

Run the cumulative local dashboard with:

```powershell
python -m uvicorn app.main:create_creative_quality_demo_app --factory --reload
```

Open `http://127.0.0.1:8000/creative-quality`. The standard sequence is
Research -> Intelligence -> Production -> Creative Quality -> explicit
founder render approval -> Local Render -> Founder Review. No live provider,
external API, audience prediction, or publishing integration is included.

## Distribution & Analytics Department v1

AuraAI can now prepare local platform metadata and manual upload checklists,
then analyze founder-supplied performance metrics and produce deterministic
learning recommendations. Publishing, authentication, uploads, API access,
ML training, and online learning remain disabled; every state transition
requires explicit founder action.

Run the cumulative local demo with:

```powershell
python -m uvicorn app.main:create_distribution_demo_app --factory --reload
```

Open `http://127.0.0.1:8000/distribution`, `/analytics`, or `/learning`.

## AI Provider Layer

AuraAI now exposes one provider-neutral registry and router for Research,
Script, Hook, Story, SEO, Marketing, Review, Image Prompt, Video Prompt,
Metadata, Audience, Analytics, Scene, Animation, and future Flow capabilities.
Employees request typed capabilities and never import a vendor implementation.

The local deterministic provider remains the default and fallback. The Gemini
adapter is disabled by default and becomes live-capable only when an explicit
composition root receives `enabled=True`, `allow_live_requests=True`, an
injected API key, and an injected transport. Provider modules do not read
environment variables, initialize clients at import time, or require the
Google SDK. Prompts are versioned typed objects; responses pass transport,
envelope, JSON, safety, schema, and AuraAI model validation.

Google AI Pro consumer access is separate from Gemini API access, billing,
project configuration, and quotas. Live use requires the appropriate Google AI
Studio or Google Cloud API configuration. API keys must be supplied through a
private runtime composition boundary and never as a visible CLI argument.

Only prompt template metadata, a deterministic prompt hash, approximate size,
token counts, latency, and safe status codes enter provider usage state. The
redaction utilities are best-effort safeguards, not a guarantee that arbitrary
sensitive input can always be detected. Cache and usage state remain in memory.

Run the network-free smoke test with:

```powershell
python -m providers.gemini.provider --smoke-test --dry-run
```

A live smoke test additionally requires both `--enable-live` and
`--founder-approved`, then requests the key through hidden interactive input.
It is never run by tests or application import. Flow and video generation are
not integrated, and provider advice cannot grant quality, rendering,
distribution, or publishing approval. AuraAI performs no automatic publishing.

The local dashboard exposes safe provider status at
`http://127.0.0.1:8000/providers`. Credentials, prompts, source documents, and
raw responses are never included in the dashboard provider projection.
