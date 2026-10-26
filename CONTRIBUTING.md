# Contributing to DC MAR SDK

Thanks for your interest in contributing! This document describes how to set up a local development environment, run tests and linters, and what we expect from pull requests.

## Quick setup

1. Fork the repository and clone your fork:

   git clone git@github.com:<your-username>/dc-mar-sdk.git
   cd dc-mar-sdk

2. Create a virtual environment and install dependencies:

   python -m venv .venv
   source .venv/bin/activate    # Windows PowerShell: .\.venv\Scripts\Activate.ps1
   pip install -e .[dev]

Optional: if your environment provides the project task runner, you can use:

   uv sync

Note: The public import namespace is `dc_mar_sdk`. CLI entry-points are `dc-mar-cli`, `dc-mar-sdk-release`, and `dc-mar-sdk-geocode-collect`.

## Common commands

- Run tests:

  uv run pytest

- Run a single test file:

  uv run pytest tests/test_some_module.py

- Formatting and linting:

  uv run ruff format .
  uv run ruff check .
  uv run mypy src/

- Run the dashboard locally:

  uv run uvicorn dc_mar_sdk.dashboard.app:app --reload

## Branches & commits

- Branch naming: `feature/<short-desc>`, `fix/<issue-number>-<short-desc>`.
- Commit messages should be short, imperative, and reference issues when relevant (e.g., "Fix issue #8: add CONTRIBUTING.md").

## Pull request checklist

Before opening a PR, ensure:

- [ ] The PR references a related issue or clearly describes the change.
- [ ] All tests pass locally (uv run pytest) and new behavior is covered by tests.
- [ ] Code is Ruff-formatted and lint-free.
- [ ] Type checks pass (mypy) where applicable.
- [ ] The PR follows the provided template and includes a clear description, testing notes, and migration notes if needed.

## Reviewing

Reviewers will focus on correctness, tests, and user-facing documentation. Keep PRs small and focused to speed review.

## Maintainers & contact

Primary maintainers

- @masonstoecker

Contact options

- Open an issue for bugs, feature requests, or general questions.
- For urgent or sensitive matters (security reports, release coordination), see the CODEOWNERS file or open a private GitHub Security Advisory. Do not post security issues publicly.

Response expectations: maintainers aim to acknowledge issues or requests within 3 business days. If you need a faster response, mention it in the issue title and label it `urgent`.

