"""Release quality gate runner.

Runs:
1. Ruff lint checks
2. Unit tests
3. Optional local smoke test
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from dc_mar_sdk.settings import get_settings

SETTINGS = get_settings()


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, check=True, cwd=cwd)


def _is_ignored_path(path: Path) -> bool:
    ignored = {".git", ".venv", ".uv", "node_modules"}
    return any(part in ignored for part in path.parts)


def find_hygiene_artifacts(root_dir: Path) -> list[Path]:
    artifacts: list[Path] = []

    for cache_dir in root_dir.rglob("__pycache__"):
        if not _is_ignored_path(cache_dir):
            artifacts.append(cache_dir)
    for pyc_file in root_dir.rglob("*.pyc"):
        if not _is_ignored_path(pyc_file):
            artifacts.append(pyc_file)
    for cache_dir in (".pytest_cache", ".ruff_cache"):
        p = root_dir / cache_dir
        if p.exists():
            artifacts.append(p)

    unique = sorted(set(artifacts), key=lambda p: str(p))
    return unique


def enforce_hygiene(root_dir: Path, fix_hygiene: bool) -> int:
    artifacts = find_hygiene_artifacts(root_dir)
    if not artifacts:
        return 0

    if fix_hygiene:
        for path in artifacts:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        print(f"==> Removed {len(artifacts)} hygiene artifact(s)")
        return 0

    print("Error: repository hygiene check failed. Found generated artifacts:", file=sys.stderr)
    for path in artifacts[:100]:
        print(f"  - {path.relative_to(root_dir)}", file=sys.stderr)
    if len(artifacts) > 100:
        print(f"  ... and {len(artifacts) - 100} more", file=sys.stderr)
    print("Run with --fix-hygiene to remove them automatically.", file=sys.stderr)
    return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run release quality checks (lint, unit tests, optional smoke test)."
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run local drift smoke test after lint + unit tests.",
    )
    parser.add_argument(
        "--api-key",
        default=SETTINGS.mar_api_key,
        help="API key for smoke test (or set DC_MAR_API_KEY).",
    )
    parser.add_argument(
        "--swagger-file",
        default=f"{SETTINGS.swagger_dir}/{SETTINGS.swagger_file_name}",
        help="Swagger file path for smoke test.",
    )
    parser.add_argument(
        "--fix-hygiene",
        action="store_true",
        help="Remove generated artifacts (__pycache__, *.pyc, lint/test caches) before checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_dir = Path(__file__).resolve().parents[3]

    hygiene_status = enforce_hygiene(root_dir, args.fix_hygiene)
    if hygiene_status != 0:
        return hygiene_status

    print("==> Running Ruff lint checks")
    run(["uv", "run", "--extra", "dev", "ruff", "check", "src", "tests"], cwd=root_dir)

    print("==> Running unit tests")
    run(["uv", "run", "--extra", "test", "pytest", "tests", "-q"], cwd=root_dir)

    if args.smoke:
        if not args.api_key:
            print("Error: --smoke requires --api-key or DC_MAR_API_KEY", file=sys.stderr)
            return 2
        print("==> Running local drift smoke test")
        run(
            [
                "uv",
                "run",
                "dc-mar-sdk-cli",
                "drift-smoke",
                "--api-key",
                args.api_key,
                "--swagger-file",
                args.swagger_file,
            ],
            cwd=root_dir,
        )

    print("✅ Release checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
