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
