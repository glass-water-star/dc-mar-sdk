Release policy and checklist
=============================

Purpose
-------
This document describes release/versioning discipline for DC MAR SDK, the semantic versioning rules we follow, and a concise checklist to produce a quality release.

Versioning
----------
We follow Semantic Versioning 2.0.0 (https://semver.org/): MAJOR.MINOR.PATCH
- MAJOR: incompatible API changes (breaking changes to public library or CLI behavior).
- MINOR: added functionality in a backwards-compatible manner (new features, public API additions).
- PATCH: backwards-compatible bug fixes and documentation, tests, or build changes.

Release flow (recommended)
--------------------------
1. Update CHANGELOG.md: add an "Unreleased" section entry describing the change.
2. Bump version in pyproject.toml (project.version). Use the next semver for the change.
3. Run the release quality gate locally:
   - uv run dc-mar-sdk-release  # preferred public script name (legacy: dc-mar-sdk-release still available)
   - If generated artifacts are present: uv run dc-mar-sdk-release --fix-hygiene
   - For a local smoke test: uv run dc-mar-sdk-release --smoke --api-key "$DC_MAR_API_KEY"
   This runs repository hygiene checks, Ruff formatting/lint checks, and pytest and will exit non-zero on failures.
4. Commit the version bump and changelog update:
   - git add pyproject.toml CHANGELOG.md
   - git commit -m "chore(release): vX.Y.Z"
5. Create an annotated tag and push:
   - git tag -a vX.Y.Z -m "Release vX.Y.Z"
   - git push origin main --follow-tags
6. Create a GitHub release using the changelog entry for vX.Y.Z (copy the entry under the single-version header).
7. Publish packages (if releasing to PyPI):
   - Local/manual publish (token required):
     - python -m build
     - python -m twine upload dist/*  # twine will prompt for credentials; prefer using an API token
     - Recommended non-interactive upload using a PyPI API token in the environment:
       - export PYPI_API_TOKEN="<token>"
       - python -m twine upload -u __token__ -p "$PYPI_API_TOKEN" dist/*
   - Automated publish (GitHub Actions):
     - Configure the `pypi` GitHub Actions environment as a PyPI trusted publisher
       for this repository and the `dc-mar-sdk` project. This is a one-time PyPI
       configuration; no long-lived PyPI API token is stored in GitHub.
     - Push an annotated tag (see checklist step 5); the release workflow builds
       and publishes the wheel using GitHub's short-lived OIDC identity.
     - See `.github/workflows/publish.yml` for the pinned trusted-publishing action.
   - Alternatively use your normal publishing flow (hatch publish, custom CI, etc.)

Quality gates (what dc-mar-sdk-release runs)
------------------------------------------
- Ruff formatting and lint checks over the repository
- Strict mypy checks over the package source
- Repository hygiene check (fails on generated artifacts like __pycache__, *.pyc, .pytest_cache, .ruff_cache unless `--fix-hygiene` is used)
- Pytest unit test suite (tests/)
- Optional local smoke test (CLI drift-smoke) when `--smoke` is passed and DC_MAR_API_KEY provided

Checklist (copy this when performing a release)
-----------------------------------------------
- [ ] Update CHANGELOG.md (Unreleased -> vX.Y.Z) with date and details
- [ ] Bump pyproject.toml version to vX.Y.Z
- [ ] Run `uv run dc-mar-sdk-release` (preferred) and fix any issues
- [ ] If hygiene check fails, run `uv run dc-mar-sdk-release --fix-hygiene`
- [ ] Run `uv run dc-mar-sdk-release --smoke --api-key "$DC_MAR_API_KEY"` (optional)
- [ ] Commit version & changelog changes
- [ ] Tag release: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
- [ ] Push branch & tags
- [ ] Create GitHub release and paste changelog notes
- [ ] Publish to PyPI (if applicable)

Notes
-----
- Keep changelog entries concise and factual. Use categories: Added, Changed, Fixed.
- For library releases, prioritize API stability: clearly document breaking changes in the MAJOR release notes.
- CI should mirror local `dc-mar-sdk-release` checks in automation for PR gating and release pipelines.

Deprecation & compatibility policy
---------------------------------
We follow Semantic Versioning (SemVer) and provide clear deprecation guidance to minimize user disruptions.

Deprecation rules
- Deprecate-before-remove: Public APIs or behavior that will be removed must be deprecated in a MINOR release before removal. Mark the API as deprecated in docs, changelog, and runtime (see below).
- Deprecation window: Maintain deprecated APIs for at least one MINOR release cycle (or a minimum of 3 months) before removing them in the next MAJOR release.
- Changelog & migration notes: Every deprecation entry must include rationale, recommended migration steps, and example code in CHANGELOG.md and relevant docs.
- Runtime warnings: Emit Python DeprecationWarning (or equivalent) when deprecated APIs are used. Warnings should reference the release where deprecation was announced and the planned removal MAJOR version.

Compatibility guarantees
- PATCH releases: Only bug fixes, documentation, and non-behavioral changes. Fully backward compatible.
- MINOR releases: New features and non-breaking API additions. Backward compatible with previous MINOR releases of the same MAJOR.
- MAJOR releases: May include breaking changes and removals of previously deprecated APIs. Provide comprehensive migration notes and upgrade guidance.

CLI & flags
- CLI flags/options that are deprecated will be documented, left in place for at least one MINOR release, and emit a clear warning when used. Removal occurs only in a MAJOR release.

Process for breaking changes
- All breaking changes must be reviewed and approved in a release PR with clear changelog entries and migration examples. The release checklist (above) must include confirmation that deprecation requirements were met prior to removal.

This policy aims to balance forward progress with stability for integrators and downstream consumers.
