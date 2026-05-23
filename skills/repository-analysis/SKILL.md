---
name: repository-analysis
description: Scan a repository, detect frameworks, identify entry points, and classify important files without executing project code.
inputs:
  - repository_path
  - repository_url
outputs:
  - framework_inventory
  - language_profile
  - entry_points
  - important_files
  - confidence
---

# Repository Analysis Skill

## Mission

Build the factual base layer for CodeSherpa. This skill reads the repository tree, dependency manifests, README files, and common entry-point locations to determine what kind of system the repository is.

## Procedure

1. Confirm the checkout exists and is a git repository.
2. Walk the file tree with the configured ignore list.
3. Detect languages from file extensions.
4. Parse manifests such as `package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, and `pom.xml`.
5. Detect frameworks only from manifest evidence or canonical config files.
6. Identify entry points such as `app/`, `pages/`, `src/main.*`, `main.py`, `backend/main.py`, `server.*`, and `api/`.
7. Rank important files by role: overview, configuration, routing, data, auth, tests, and deployment.
8. Return confidence with every high-level inference.

## Guardrails

- Do not execute repository code.
- Do not run package managers.
- Do not infer a framework from directory names alone when manifest evidence is absent.
- When a file is too large to inspect, record its path and reason.
