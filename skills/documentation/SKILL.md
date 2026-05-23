---
name: documentation
description: Generate repository summaries, onboarding explanations, and documentation improvements from analysis evidence.
inputs:
  - repository_scan
  - architecture_summary
outputs:
  - repo_summary
  - documentation_gaps
  - explanation_blocks
  - recommendations
---

# Documentation Skill

## Mission

Create concise explanations that help humans learn the repository. Documentation should reveal what the system does, where to look, and what to change first.

## Procedure

1. Summarize the project using README and manifest evidence.
2. Highlight architecture and entry points.
3. Identify missing docs when README, contribution guide, or setup instructions are absent.
4. Generate contributor-friendly explanations.
5. Store durable summary facts in memory.

## Voice

Clear, calm, and practical. Use repository-specific evidence and avoid performative certainty.
