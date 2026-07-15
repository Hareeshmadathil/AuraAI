# AuraAI

AuraAI is a founder-controlled AI media operating system. It coordinates typed
executives, directors, specialists, missions, workflows, provider routing,
content production, creative review, local rendering, distribution preparation,
and manually supplied analytics through one local command center.

AuraAI is under active development. It does not claim profitability, complete
autonomy, automatic publishing, live platform analytics, or public-service
readiness.

## Current project status

The repository provides deterministic end-to-end demonstrations, explicit
runtime state, a local FastAPI dashboard, quality and approval gates, a local
render pilot, manual distribution preparation, and a provider-neutral AI layer.
Network-backed Gemini requests are optional, disabled by default, and require
explicit founder approval.

The dashboard is local and unauthenticated. Keep it bound to a trusted local
interface. Rendered artifacts require human review and publishing remains
manual.

## Founder-controlled philosophy

AuraAI can prepare research, recommendations, scripts, production packages,
review evidence, render plans, upload checklists, and learning reports. It does
not grant itself consequential approvals. Quality approval does not imply render
approval, and render approval does not imply distribution or publishing
approval.

## Architecture

```text
Founder
  └── Aura CEO
      └── Orion COO
          └── Department Directors
              └── Specialists
                  └── Tasks → Workflows → Mission state
```

The runtime engine coordinates typed records, events, scheduling, state, and
dashboard projections. Dependencies are injected at composition boundaries;
provider and production implementations are replaceable.

## Departments

- Executive and Strategy
- Research
- Intelligence
- Marketing and SEO
- Production
- Creative Quality
- Distribution
- Analytics and Learning
- Operations and System

## Employees

The current deterministic roster contains 40 implemented employees: two
executives, seven department directors, and 31 specialists. The dashboard builds
employee cards from roster/runtime data rather than hard-coding identities in
templates.

## End-to-end pipeline

```text
Research
  → Intelligence
  → Production
  → Creative Quality
  → Founder render approval
  → Local Render
  → Founder review
  → Distribution preparation
  → Manual upload
  → Manual metrics import
  → Analytics and Learning
```

Each demonstration is deterministic unless a live provider is explicitly
enabled. Sample data is visibly labelled and must not be interpreted as real
market or performance data.

## AI provider layer

Employees request typed capabilities through the provider-neutral registry and
router. The deterministic provider is the default and fallback. Provider usage
state records safe operational metadata rather than prompts, source documents,
credentials, or raw responses.

Supported typed capability boundaries include research, script, hook, story,
SEO, marketing, review, image/video prompts, metadata, audience, analytics,
scene, animation, and future Flow work. Flow is not integrated.

## Gemini integration

The Gemini adapter uses a transport-injected GenerateContent integration. It is
disabled unless a private composition boundary supplies an API key and enables
both live requests and founder approval. The provider does not read `.env`
directly, initialize a client on import, or expose the key through CLI arguments.

Google AI Pro consumer access is separate from Gemini API access, project
configuration, quotas, and billing. The network-free smoke test is:

```powershell
python -m providers.gemini.provider --smoke-test --dry-run
```

A live smoke test requires both `--enable-live` and `--founder-approved`, then
requests the key through hidden interactive input. Tests never perform live
requests.

## Real Mission Pilot v1

The Real Mission Pilot connects the Mission Execution Engine to existing
Research, SEO, Production script, Creative Quality, runtime-event, and dashboard
boundaries. Its deterministic default produces typed versioned research, SEO,
script, quality, and founder-review artifacts, then stops at `FOUNDER_REVIEW`.

```text
CREATED → PLANNING → RESEARCH → SEO → SCRIPT → FOUNDER_REVIEW
```

Completion requires an explicit founder decision. Quality blockers prevent
approval. Optional live Gemini advice can only be composed with an injected
provider router and a separate explicit founder approval; the demo factory
never constructs a live client. This milestone does not render or publish.

## First Real Content Mission v1

The first-content mission composes the Mission Execution Engine and Real Content
Pilot into a complete founder-review package: research, SEO, versioned script,
production plans, Creative Quality results, thumbnails, short-form derivatives,
metadata, evidence warnings, and a checksum manifest. The sample specification
is `founder_inputs/first_content_mission.example.json`; it is sample data, not a
selected flagship niche.

Validate the input without executing or writing artifacts:

```powershell
python -m company_missions.first_real_content.cli --input founder_inputs/first_content_mission.example.json --output-root outputs/missions --dry-run
```

Run the deterministic mission and explicitly export beneath the ignored output
root:

```powershell
python -m company_missions.first_real_content.cli --input founder_inputs/first_content_mission.example.json --output-root outputs/missions --execute
```

Live Gemini remains opt-in and requires both `--enable-live-gemini` and
`--founder-approved-live-ai`, an interactive founder confirmation, and a hidden
key prompt. The request budget defaults to six: at most one request for each
supported research, SEO, script, hook, review, and metadata stage. Deterministic
fallback remains available. Prompts, raw responses, credentials, and
authorization data are not exported.

The mission always stops at `FOUNDER_REVIEW`. Content approval does not approve
rendering, uploading, or publishing. Review the local page with:

```powershell
python -m uvicorn app.main:create_first_content_mission_demo_app --factory --reload
```

## Local rendering

The Production v2 pilot detects local FFmpeg, FFprobe, and Windows speech
support at runtime. It does not download assets or call external services.
Explicit rendering can produce review MP4, vertical video, PNG thumbnail, WAV
narration, SRT/VTT captions, and a JSON manifest beneath ignored output paths.

```powershell
python -m production.rendering.pipeline --demo --founder-render-approved --output-root outputs/production
```

Use `--silent-fallback` only when a visibly silent review artifact is acceptable.
Existing output directories are protected unless `--overwrite` is supplied.

## Private Video Production v1

The private-video layer turns an approved Mission Zero package into a local,
founder-reviewed audiovisual production plan. Content approval, private-render
approval, and publishing approval are independent. This milestone never grants
publishing approval and every rendered draft is visibly marked `INTERNAL REVIEW`
and `NOT FOR PUBLICATION`.

The implementation uses installed Windows System.Speech voices when available,
the existing subtitle wrapping logic, founder-supplied evidence assets, clearly
labelled deterministic placeholders, and an injected local FFmpeg/FFprobe
renderer. It does not download voices, footage, music, or models. Background
music is optional and requires founder-supplied license metadata.

```powershell
python -m private_video_production.cli --check-environment
python -m private_video_production.cli --list-voices
python -m private_video_production.cli --mission-package "outputs/mission-zero-revision/f7385664-ac50-4e16-83c1-339781135a0a" --output-root outputs/private-video --prepare
```

Review the generated founder capture pack before selecting an installed voice.
Full narration requires explicit content approval and founder confirmation.
Rendering additionally requires private-render approval. A 720p placeholder
preview and a 1080p private draft are supported; neither operation uploads or
publishes. See `docs/private-video-production/` for the exact workflow,
limitations, and safety boundaries.

## Creative quality

The Creative Quality stage scores deterministic heuristics for hook, story,
pacing, retention, clarity, motion, subtitles, thumbnail, factuality, trust,
call to action, and completeness. These scores do not predict views, retention,
click-through rate, subscribers, or revenue.

Low-risk subjective variance can require founder override. Factuality, trust,
safety, copyright, and security blockers cannot be overridden.

## Distribution and analytics

Distribution produces local metadata and upload checklists. It does not
authenticate to social platforms, create accounts, upload, or publish.
Analytics accepts founder-supplied metrics and computes deterministic reports;
it does not retrieve live platform data. Learning recommendations do not train
or update a model automatically.

## Dashboard

The FastAPI and Jinja2 dashboard projects explicitly injected in-memory state.
It preserves company roster, missions, workflows, decisions, intelligence,
production, quality, render artifacts, distribution, analytics, learning, and
safe provider health across cumulative demo factories.

The brand review page at `/brand` presents three local SVG concept families,
design tokens, and component samples. Every logo is an unapproved concept.

## Installation

AuraAI targets Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

No dependency installation is required when reviewing documentation or SVG
assets alone.

## Running the main demo factories

Safe empty dashboard:

```powershell
python -m uvicorn app.main:app --reload
```

Deterministic company dashboard:

```powershell
python -m uvicorn app.main:create_demo_app --factory --reload
```

Stage-specific cumulative demonstrations:

```powershell
python -m uvicorn app.main:create_niche_discovery_demo_app --factory --reload
python -m uvicorn app.main:create_intelligence_demo_app --factory --reload
python -m uvicorn app.main:create_content_production_demo_app --factory --reload
python -m uvicorn app.main:create_creative_quality_demo_app --factory --reload
python -m uvicorn app.main:create_local_render_demo_app --factory --reload
python -m uvicorn app.main:create_quality_render_demo_app --factory --reload
python -m uvicorn app.main:create_distribution_demo_app --factory --reload
python -m uvicorn app.main:create_real_content_pilot_demo_app --factory --reload
python -m uvicorn app.main:create_first_content_mission_demo_app --factory --reload
```

Open `http://127.0.0.1:8000`. Useful local pages include `/`, `/employees`,
`/intelligence`, `/production`, `/creative-quality`, `/renders`,
`/distribution`, `/analytics`, `/learning`, `/providers`, and `/brand`.
The deterministic pilot review is available at `/mission-pilot`; the complete
first-content review is at `/first-content-mission`. Its mission is
also projected on `/missions` and its existing cumulative state remains visible
on `/workflows`, `/decisions`, and `/creative-quality`.

## Testing

Run the complete suite after every change:

```powershell
python -m pytest -q
```

Tests use deterministic providers and injected transports. They do not require
real environment secrets or external network access.

## Security

- Never commit `.env`, credentials, generated media, runtime databases, or logs.
- Supply provider keys only through private runtime boundaries.
- Keep the unauthenticated dashboard on a trusted local interface.
- Treat rendered assets and generated claims as review-required.
- Use registered artifact identifiers; do not expose arbitrary filesystem paths.
- Preserve founder approval gates for rendering, distribution, and publishing.

## Limitations

- No automatic publishing or platform account management.
- No live social-platform analytics ingestion.
- No Flow integration.
- No database-backed dashboard state or authentication.
- No guarantee that provider responses, quality scores, or research predict
  commercial performance.
- Real Mission Pilot research uses supplied notes and provider synthesis only;
  external evidence verification remains a founder responsibility.
- Brand concepts have not received founder selection or trademark clearance.

## Roadmap

Near-term work should prioritize founder-approved, revenue-focused content
operations: validate a niche with live evidence, complete one reviewed content
package, render locally, upload manually, import real metrics, and use the
learning report to guide the next iteration. Public deployment, automated
publishing, and independent channel branding remain later decisions.

## Legacy Media Processing Foundation

AuraAI began as an Automated YouTube Agent experiment for transforming a source
video into reusable short-form media. That foundation introduced downloader,
audio extraction, transcription, content analysis, clip finding, editing,
caption, thumbnail, SEO, and publishing-agent concepts.

The current platform preserves useful local media-processing and transcription
ideas while placing them inside a larger typed company architecture with
missions, departments, runtime orchestration, quality gates, provider routing,
founder approvals, local rendering, and deterministic dashboard state. Legacy
workflows do not imply permission to download, transform, or publish content
without rights and review.

## Founder

AuraAI was founded by **Hareesh Madathil**.
