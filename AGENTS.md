# Repository Guidelines

## Keep Work Lightweight

- This is a personal project. Make the smallest change that solves the current problem, reuse existing code, and follow nearby style.
- Reserve new abstractions, dependencies, test suites, branches, and CI changes for concrete needs. Use the current checkout for routine edits. Commit or push only when requested.
- Preserve local changes and emulator data. Keep the existing session handoff current when the work or next step changes.

## Current Setup

- The Windows baseline is MaaFramework `v6.0.0-beta.3` (`MaaFw==6.0.0b3`) with MXU `v2.11.2`. Launch `install/mxu.exe`. The packaged Agent uses `install/.venv`. See the [README](README.md) for setup and repackaging.
- Task entries are in `assets/interface.json`, pipelines in `assets/resource/pipeline/`, and Python custom logic in `agent/custom/`. Register custom actions and recognizers in `agent/CustomFile.py` and match those names in the pipeline.

## Check What Changed

- Review the diff. Use `npx @nekosu/maa-tools check` for pipeline edits and check the affected step on MuMu when emulator behavior changes. Report what actually ran.
