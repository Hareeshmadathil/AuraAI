# AuraAI Development Guide

AuraAI is a fully autonomous AI Creator Operating System.

## Goal

Build a company of AI employees capable of running a complete content business.

Every feature must be:

- modular
- testable
- production ready
- fully typed
- documented

---

# Development Rules

Always:

- use dataclasses or Pydantic models where appropriate
- write pytest tests
- keep functions small
- never duplicate logic
- use enums instead of magic strings
- log important events
- handle exceptions

---

# Folder Structure

core/
agents/
operations/
workflows/
research_sources/
marketing/
production/
finance/
publishing/
analytics/

---

# Architecture

CEO

↓

COO

↓

Department Directors

↓

Employees

↓

Tasks

↓

Workflows

---

# Coding Style

- Python 3.12+
- PEP8
- type hints
- Google docstrings
- no global variables
- dependency injection where possible

---

# Testing

Every new module must include tests.

No feature is complete unless tests pass.

Run:

python -m pytest -q

after every change.

---

# Mission

AuraAI should eventually build, publish, market and grow social media channels autonomously.