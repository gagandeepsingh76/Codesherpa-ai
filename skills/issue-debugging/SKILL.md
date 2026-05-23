---
name: issue-debugging
description: Analyze issue text against repository structure to identify likely affected files and debugging directions.
inputs:
  - issue_title
  - issue_body
  - repository_scan
outputs:
  - likely_areas
  - affected_files
  - debugging_steps
  - confidence
---

# Issue Debugging Skill

## Mission

Connect issue language to repository areas. This skill is designed for maintainers and contributors who need a fast first debugging path.

## Procedure

1. Extract issue keywords related to auth, routing, API, state, database, build, test, deployment, or documentation.
2. Match keywords against detected important files and folder roles.
3. Suggest the smallest inspection path first.
4. Provide confidence and explain why each file or folder is relevant.

## Guardrails

- Do not claim a root cause without file evidence.
- Avoid suggesting destructive commands.
- Keep debugging steps observable and reversible.
