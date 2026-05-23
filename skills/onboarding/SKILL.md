---
name: onboarding
description: Generate beginner-friendly repository onboarding flows, learning sequence, and first contribution paths.
inputs:
  - repository_scan
  - architecture_summary
outputs:
  - onboarding_roadmap
  - beginner_files
  - contribution_order
  - recommended_first_tasks
---

# Onboarding Skill

## Mission

Help a new contributor build momentum quickly. The roadmap should be practical, sequenced, and grounded in actual repository files.

## Procedure

1. Start with overview documents and manifests.
2. Move from entry points to core folders.
3. Identify files that are useful but lower-risk for a first contribution.
4. Suggest a learning sequence with estimated difficulty.
5. Provide recommended first tasks that do not require broad architectural changes.

## Quality Bar

- Beginner guidance must point to concrete files.
- Difficulty should be honest.
- Avoid generic "read the docs" advice unless docs were detected.
