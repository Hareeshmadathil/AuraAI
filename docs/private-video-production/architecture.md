# Private Video Production v1 architecture

The layer composes existing AuraAI boundaries rather than replacing them:

```text
Approved Mission Zero script-v2 + passed Creative Quality package
  → strict package loader
  → independent founder approval record through MissionManager
  → installed local voice adapter
  → evidence-aware scene and founder capture plan
  → existing 42-character subtitle wrapping
  → deterministic timeline and audio plan
  → injected FFmpeg renderer
  → FFprobe verification
  → private founder review
```

No module initializes external clients or writes files at import time. Runtime
events carry IDs, counts, status, and version data, never scripts, credentials,
raw subprocess output, or private source documents.

The expected hardware profile is Windows 11, 4 GB RAM, and an Intel i3-8130U.
Rendering uses H.264/AAC, `yuv420p`, 30 fps, a memory-conscious preset, and no
4K or hardware-encoder requirement.
