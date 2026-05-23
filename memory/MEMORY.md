# CodeSherpa Memory

This file stores durable, human-readable memory for the CodeSherpa GitAgent.

## Operating Notes

- Repository memories are stored as compact facts, not full source code.
- Each analysis should retain repository URL, detected frameworks, architecture summary, important files, contributor notes, and confidence levels.
- User questions should be remembered only as prompts and high-level intent.

## Repository Index

The machine-readable repository index lives in `memory/repositories.json`.
