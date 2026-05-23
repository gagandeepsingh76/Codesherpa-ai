---
name: architecture-mapping
description: Convert repository scan evidence into an architecture map with folder relationships, boundaries, and dependency flow.
inputs:
  - repository_scan
outputs:
  - architecture_summary
  - boundaries
  - nodes
  - edges
  - dependency_flow
---

# Architecture Mapping Skill

## Mission

Turn detected structure into a navigable architecture map. The output should help an engineer understand how the repository is organized before opening source files.

## Procedure

1. Group top-level folders by responsibility: application, API, package, docs, tests, scripts, infra, and configuration.
2. Detect frontend/backend boundaries using framework evidence, folder names, and entry points.
3. Link manifests to source folders and source folders to tests, docs, or deployment files.
4. Explain dependency direction from manifests and import-heavy areas when available.
5. Mark uncertainty when boundaries are naming-based rather than manifest-backed.

## Output Style

- Use compact labels suitable for UI nodes.
- Explain folder relationships in direct language.
- Prefer confidence scores over absolute claims.
