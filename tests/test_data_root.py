"""DATA_ROOT / PROJECT_ROOT 必须指向持久化目录，不能落在 site-packages。"""

from __future__ import annotations

from pathlib import Path

from intern_platform.config import DATA_ROOT, PROJECT_ROOT, _detect_project_root


def test_project_root_is_repo_or_app(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("INTERN_PLATFORM_ROOT", raising=False)
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    monkeypatch.delenv("DATA_ROOT", raising=False)
    root = _detect_project_root()
    assert (root / "pyproject.toml").is_file() or (root / "apps").is_dir()
    assert "site-packages" not in root.as_posix()


def test_env_overrides_project_root(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("INTERN_PLATFORM_ROOT", str(tmp_path))
    assert _detect_project_root() == tmp_path.resolve()


def test_data_root_not_under_site_packages() -> None:
    assert "site-packages" not in DATA_ROOT.as_posix()
    assert DATA_ROOT.name == "data" or DATA_ROOT.as_posix().endswith("/data")
    assert PROJECT_ROOT.is_dir()
