# Project guide

This repository studies trajectory-conditioned, collision-risk-aware visual communication for remote robot navigation.

Before changing anything:

1. Read `docs/progress.md`.
2. Read the relevant sections of `docs/research_protocol.md` and `docs/roadmap.md`.
3. Check `git status`.
4. State the current task and its acceptance criteria.

Rules:

- Stay within the current milestone. Do not add ROS 2, WSL, CUDA, learned allocation, or real hardware unless the scope is explicitly changed.
- Treat unimplemented work as planned, stub, or not implemented.
- Never claim an experiment or test passed unless it was run.
- Use `pathlib`; do not hard-code personal absolute paths.
- Keep dependencies in `requirements.txt` and commands runnable from the repository root.
- Record durable research definitions in `docs/research_protocol.md`, execution order in `docs/roadmap.md`, decisions in `docs/decisions.md`, and verified status in `docs/progress.md`.
- Do not push or create a remote repository without explicit user approval.

At task completion, run relevant checks, update `docs/progress.md`, update `docs/decisions.md` when a choice changed, and name one next priority.

