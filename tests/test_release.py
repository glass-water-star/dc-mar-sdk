import argparse
from pathlib import Path

import pytest

from dc_mar_sdk.scripts import release


def test_find_project_root_accepts_a_nested_source_path(tmp_path: Path) -> None:
    root = tmp_path / "project"
    nested = root / "src" / "package"
    nested.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (root / "tests").mkdir()

    assert release.find_project_root(nested) == root


def test_enforce_hygiene_reports_and_removes_generated_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache_dir = tmp_path / "package" / "__pycache__"
    cache_dir.mkdir(parents=True)
    (cache_dir / "module.pyc").write_bytes(b"compiled")
    (tmp_path / ".pytest_cache").mkdir()

    assert release.enforce_hygiene(tmp_path, fix_hygiene=False) == 2
    assert "repository hygiene check failed" in capsys.readouterr().err

    assert release.enforce_hygiene(tmp_path, fix_hygiene=True) == 0
    assert not cache_dir.exists()
    assert not (tmp_path / ".pytest_cache").exists()


def test_main_stops_when_not_run_from_a_source_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "parse_args", lambda: argparse.Namespace())
    monkeypatch.setattr(release, "find_project_root", lambda _: None)

    assert release.main() == 2


def test_main_runs_all_local_checks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    arguments = argparse.Namespace(
        fix_hygiene=False,
        smoke=False,
        api_key=None,
        swagger_file="swagger/swagger.json",
    )
    commands: list[tuple[list[str], Path | None]] = []

    monkeypatch.setattr(release, "parse_args", lambda: arguments)
    monkeypatch.setattr(release, "find_project_root", lambda _: tmp_path)
    monkeypatch.setattr(release, "enforce_hygiene", lambda _, __: 0)
    monkeypatch.setattr(release, "run", lambda command, cwd=None: commands.append((command, cwd)))

    assert release.main() == 0
    assert [command for command, _ in commands] == [
        ["uv", "run", "--extra", "dev", "ruff", "format", "--check", "."],
        ["uv", "run", "--extra", "dev", "ruff", "check", "."],
        ["uv", "run", "--extra", "dev", "mypy", "src"],
        ["uv", "run", "--extra", "test", "pytest", "tests", "-q"],
    ]
    assert all(cwd == tmp_path for _, cwd in commands)
