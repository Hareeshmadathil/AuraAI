# AuraAI Color System

The source of truth is `app/dashboard/static/css/tokens.css`.

## Core roles

- Deep Ink: canvas and stable corporate foundation.
- Elevated blue-black: layered surfaces, never decorative clutter.
- Aura Aqua: identity, focus, and positive operational emphasis.
- Signal Blue: information and data relationships.
- Founder Amber: approvals and founder-attention states.

Status colors are separate from department colors. Every status includes text
or an icon; color never carries meaning alone. Danger, warning, success, idle,
working, waiting, blocked, and completed states use dedicated tokens.

Department accents are restrained card edges, badges, and chart markers. New
departments must add a named token with contrast review rather than hard-code a
new color in templates. Default dark surfaces target readable WCAG contrast;
interactive states must be checked again if tokens change. Light-mode semantic
names are prepared, but a full light theme is not part of version 1.
