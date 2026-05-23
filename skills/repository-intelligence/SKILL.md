---
name: repository-intelligence
description: Score repository complexity, identify dependency and onboarding risks, map ownership surfaces, and generate good-first-issue candidates.
inputs:
  - repository_scan
  - architecture_map
outputs:
  - complexity_score
  - risk_insights
  - ownership_map
  - dependency_insights
  - good_first_issues
  - contribution_paths
---

# Repository Intelligence Skill

## Mission

Turn repository analysis into contributor strategy. This skill answers: how hard is this repo to enter, where are the safest first contributions, which areas likely belong to which owners, and what risks could slow down onboarding?

## Procedure

1. Score complexity using file count, language count, framework signals, entry points, manifests, and top-level folder surfaces.
2. Identify deterministic risk signals such as missing onboarding docs, missing tests, missing lockfiles, high framework surface area, or absent CI workflows.
3. Group folders into ownership surfaces: frontend, backend, shared/core, data, docs, tests, and infrastructure.
4. Inspect manifests for dependency ecosystem signals and reproducibility risks.
5. Generate good-first-issue ideas only when they can be grounded in detected files or folders.
6. Produce contribution paths that are sequenced, scoped, and realistic for first-time contributors.

## Guardrails

- Do not invent maintainers, teams, or ownership identities.
- Use owner hints, not definitive owner claims.
- Do not recommend changing core architecture as a first contribution.
- Every issue candidate must reference at least one detected file or folder.
