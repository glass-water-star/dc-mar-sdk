# Changelog

All notable changes to this project will be documented in this file.

The format is based on "Keep a Changelog" (https://keepachangelog.com/en/1.0.0/) and this project adheres to Semantic Versioning (https://semver.org/).

## [Unreleased]
### Added
- Release documentation (RELEASE_POLICY.md) and changelog scaffold.
- Release quality gate runner: `dc-mar-sdk-release` (preferred public script name; legacy `dc-mar-sdk-release` still available) — runs lint + unit tests + optional smoke test.
- CLI command discovery/contract rejection and release-gate hygiene/check
  sequencing regression coverage.

### Changed
- Replaced Black with Ruff formatting, expanded Ruff lint coverage, and made
  Ruff formatting plus linting mandatory in CI and the release quality gate.
- Added strict mypy enforcement to CI and the release quality gate, with typed
  cache, telemetry, client, dashboard, CLI, Swagger, and drift boundaries.
- Hardened GitHub Actions with immutable action revisions, locked dependency
  synchronization, and PyPI trusted publishing through short-lived OIDC tokens.

### Fixed
- Invalid cached autocomplete payloads are now evicted and refetched instead of
  being returned to callers.

## [0.1.0] - 2026-07-18
### Added
- Initial public release and library scaffolding:
  - Type-safe API client generated from the OpenAPI spec
  - Pluggable caching backends (SQLite default, Redis, in-memory)
  - Request telemetry and tracking
  - Web dashboard (FastAPI) and CLI tool
  - Release quality checks (ruff linting, pytest unit tests, optional local smoke test)
