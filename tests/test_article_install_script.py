from __future__ import annotations

import json
from pathlib import Path
import sys

import install_article_local as installer
import pytest


def test_install_local_app_requires_skip_init_when_no_deps(tmp_path):
    with pytest.raises(RuntimeError, match="--no-deps"):
        installer.install_local_app(
            python_executable=sys.executable,
            venv_dir=tmp_path / "venv",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "runtime",
            no_deps=True,
            skip_init=False,
        )


def test_install_local_app_resolves_python_executable_from_path_lookup(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    discovered_python = tmp_path / "bin" / "python3.12"
    discovered_python.parent.mkdir(parents=True, exist_ok=True)
    discovered_python.write_text("", encoding="utf-8")

    def fake_run(command, *, cwd=None, capture_output=False, env=None):
        command = list(command)
        calls.append(command)
        if command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            python_path = installer._venv_python(venv_dir)
            script_path = installer._venv_script(venv_dir, "article-local")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")
            return None
        return type("Completed", (), {"stdout": "{}"})()

    monkeypatch.setattr(installer.shutil, "which", lambda name: str(discovered_python) if name == "python3.12" else None)
    monkeypatch.setattr(installer, "_run", fake_run)

    installer.install_local_app(
        python_executable="python3.12",
        venv_dir=tmp_path / "venv",
        state_root=tmp_path / "state",
        runtime_root=tmp_path / "runtime",
        write_env=tmp_path / "article-local.env",
    )

    assert calls[0][0] == str(discovered_python.resolve())


def test_install_local_app_no_deps_skip_init_builds_expected_commands(monkeypatch, tmp_path):
    calls: list[dict[str, object]] = []

    def fake_run(command, *, cwd=None, capture_output=False, env=None):
        command = list(command)
        calls.append({"command": command, "cwd": cwd, "capture_output": capture_output, "env": env})
        if command[:3] == [sys.executable, "-m", "venv"] or command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            python_path = installer._venv_python(venv_dir)
            script_path = installer._venv_script(venv_dir, "article-local")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")
        return None

    monkeypatch.setattr(installer, "_run", fake_run)

    payload = installer.install_local_app(
        python_executable=sys.executable,
        venv_dir=tmp_path / "venv",
        state_root=tmp_path / "state",
        runtime_root=tmp_path / "runtime",
        write_env=tmp_path / "article-local.env",
        no_deps=True,
        skip_init=True,
    )

    assert payload["status"] == "ok"
    assert payload["install"]["mode"] == "editable"
    assert payload["install"]["no_deps"] is True
    assert payload["install"]["skip_init"] is True
    assert payload["venv"]["system_site_packages"] is True
    assert payload["init"] is None
    assert payload["distribution"]["wheel_path"] is None
    assert payload["quickstart"]["doctor"].endswith("article-local doctor --state-root "
                                                    f"{tmp_path / 'state'} --runtime-root {tmp_path / 'runtime'}")
    assert payload["quickstart"]["serve"].endswith("article-local serve --state-root "
                                                   f"{tmp_path / 'state'} --runtime-root {tmp_path / 'runtime'}")
    assert "--system-site-packages" in calls[0]["command"]
    assert "--no-deps" in calls[1]["command"]
    assert calls[1]["cwd"] == installer.PROJECT_ROOT
    assert calls[1]["env"]["PYTHONPATH"]


def test_install_local_app_runs_init_and_parses_payload(monkeypatch, tmp_path):
    calls: list[dict[str, object]] = []

    def fake_run(command, *, cwd=None, capture_output=False, env=None):
        command = list(command)
        calls.append({"command": command, "cwd": cwd, "capture_output": capture_output, "env": env})
        if command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            python_path = installer._venv_python(venv_dir)
            script_path = installer._venv_script(venv_dir, "article-local")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")
            return None
        if command[0].endswith("article-local"):
            return type(
                "Completed",
                (),
                {
                    "stdout": json.dumps(
                        {
                            "status": "ok",
                            "summary": {
                                "headline": "本地运行壳初始化完成。",
                                "next_steps": [
                                    "article-local doctor --state-root /tmp/state --runtime-root /tmp/runtime",
                                    "article-local serve --state-root /tmp/state --runtime-root /tmp/runtime",
                                ],
                            },
                        },
                        ensure_ascii=False,
                    )
                },
            )()
        return None

    monkeypatch.setattr(installer, "_run", fake_run)

    payload = installer.install_local_app(
        python_executable=sys.executable,
        venv_dir=tmp_path / "venv",
        state_root=tmp_path / "state",
        runtime_root=tmp_path / "runtime",
        write_env=tmp_path / "article-local.env",
        overwrite_env=True,
    )

    assert payload["init"]["summary"]["headline"] == "本地运行壳初始化完成。"
    assert payload["install"]["mode"] == "editable"
    assert payload["quickstart"]["doctor"].startswith("article-local doctor")
    assert payload["quickstart"]["serve"].startswith("article-local serve")
    assert calls[2]["capture_output"] is True
    assert "--write-env" in calls[2]["command"]
    assert "--overwrite-env" in calls[2]["command"]


def test_install_local_app_wheel_mode_builds_artifact_and_installs_from_direct_url(monkeypatch, tmp_path):
    calls: list[dict[str, object]] = []
    built_wheel = tmp_path / "dist" / "thesis_format_tool-0.1.0-py3-none-any.whl"

    def fake_run(command, *, cwd=None, capture_output=False, env=None):
        command = list(command)
        calls.append({"command": command, "cwd": cwd, "capture_output": capture_output, "env": env})
        if command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            python_path = installer._venv_python(venv_dir)
            script_path = installer._venv_script(venv_dir, "article-local")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")
            return None
        if command[3] == "wheel":
            built_wheel.parent.mkdir(parents=True, exist_ok=True)
            built_wheel.write_bytes(b"wheel-bytes")
            return None
        return None

    monkeypatch.setattr(installer, "_run", fake_run)

    payload = installer.install_local_app(
        python_executable=sys.executable,
        venv_dir=tmp_path / "venv",
        state_root=tmp_path / "state",
        runtime_root=tmp_path / "runtime",
        write_env=tmp_path / "article-local.env",
        no_deps=True,
        skip_init=True,
        install_mode="wheel",
        artifact_dir=tmp_path / "dist",
    )

    assert payload["install"]["mode"] == "wheel"
    assert payload["install"]["operation"] == "install"
    assert payload["install"]["build_command"] is not None
    assert payload["distribution"]["wheel_path"] == str(built_wheel.resolve())
    assert payload["distribution"]["history"]["entries"][-1]["wheel_path"] == str(built_wheel.resolve())
    assert calls[1]["command"][3] == "wheel"
    assert "--wheel-dir" in calls[1]["command"]
    assert calls[2]["command"][3] == "install"
    assert "--force-reinstall" in calls[2]["command"]
    assert calls[2]["command"][-1] == (
        f"thesis-format-tool[api] @ {built_wheel.resolve().as_uri()}"
    )


def test_install_local_app_rejects_unknown_install_mode(tmp_path):
    with pytest.raises(RuntimeError, match="Unsupported install mode"):
        installer.install_local_app(
            python_executable=sys.executable,
            venv_dir=tmp_path / "venv",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "runtime",
            skip_init=True,
            no_deps=True,
            install_mode="zipapp",
        )


def test_install_local_app_rejects_upgrade_and_rollback_together(tmp_path):
    with pytest.raises(RuntimeError, match="cannot be used together"):
        installer.install_local_app(
            python_executable=sys.executable,
            venv_dir=tmp_path / "venv",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "runtime",
            skip_init=True,
            no_deps=True,
            upgrade=True,
            rollback=True,
        )


def test_install_local_app_upgrade_forces_wheel_mode(monkeypatch, tmp_path):
    calls: list[dict[str, object]] = []
    built_wheel = tmp_path / "dist" / "thesis_format_tool-0.2.0-py3-none-any.whl"

    def fake_run(command, *, cwd=None, capture_output=False, env=None):
        command = list(command)
        calls.append({"command": command, "cwd": cwd, "capture_output": capture_output, "env": env})
        if command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            python_path = installer._venv_python(venv_dir)
            script_path = installer._venv_script(venv_dir, "article-local")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")
            return None
        if command[3] == "wheel":
            built_wheel.parent.mkdir(parents=True, exist_ok=True)
            built_wheel.write_bytes(b"wheel-bytes")
            return None
        return None

    monkeypatch.setattr(installer, "_run", fake_run)

    payload = installer.install_local_app(
        python_executable=sys.executable,
        venv_dir=tmp_path / "venv",
        state_root=tmp_path / "state",
        runtime_root=tmp_path / "runtime",
        write_env=tmp_path / "article-local.env",
        no_deps=True,
        skip_init=True,
        upgrade=True,
        artifact_dir=tmp_path / "dist",
    )

    assert payload["install"]["mode"] == "wheel"
    assert payload["install"]["operation"] == "upgrade"
    assert payload["distribution"]["wheel_path"] == str(built_wheel.resolve())
    assert payload["distribution"]["history"]["entries"][-1]["operation"] == "upgrade"
    assert calls[1]["command"][3] == "wheel"
    assert calls[2]["command"][3] == "install"


def test_install_local_app_rollback_requires_previous_history(tmp_path):
    with pytest.raises(RuntimeError, match="No previous wheel install is available for rollback"):
        installer.install_local_app(
            python_executable=sys.executable,
            venv_dir=tmp_path / "venv",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "runtime",
            write_env=tmp_path / "article-local.env",
            no_deps=True,
            skip_init=True,
            rollback=True,
            artifact_dir=tmp_path / "dist",
        )


def test_install_local_app_rollback_reinstalls_previous_wheel(monkeypatch, tmp_path):
    calls: list[dict[str, object]] = []
    artifact_dir = tmp_path / "dist"
    current_wheel = artifact_dir / "thesis_format_tool-0.2.0-py3-none-any.whl"
    previous_wheel = artifact_dir / "thesis_format_tool-0.1.0-py3-none-any.whl"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    current_wheel.write_bytes(b"current")
    previous_wheel.write_bytes(b"previous")
    installer._write_install_history(
        artifact_dir,
        {
            "current_index": 1,
            "entries": [
                {
                    "installed_at": "2026-04-25T00:00:00Z",
                    "operation": "install",
                    "wheel_path": str(previous_wheel.resolve()),
                    "extras": "api",
                    "venv_dir": str((tmp_path / "venv").resolve()),
                },
                {
                    "installed_at": "2026-04-26T00:00:00Z",
                    "operation": "upgrade",
                    "wheel_path": str(current_wheel.resolve()),
                    "extras": "api",
                    "venv_dir": str((tmp_path / "venv").resolve()),
                },
            ],
        },
    )

    def fake_run(command, *, cwd=None, capture_output=False, env=None):
        command = list(command)
        calls.append({"command": command, "cwd": cwd, "capture_output": capture_output, "env": env})
        if command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            python_path = installer._venv_python(venv_dir)
            script_path = installer._venv_script(venv_dir, "article-local")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")
            return None
        return None

    monkeypatch.setattr(installer, "_run", fake_run)

    payload = installer.install_local_app(
        python_executable=sys.executable,
        venv_dir=tmp_path / "venv",
        state_root=tmp_path / "state",
        runtime_root=tmp_path / "runtime",
        write_env=tmp_path / "article-local.env",
        no_deps=True,
        skip_init=True,
        install_mode="wheel",
        rollback=True,
        artifact_dir=artifact_dir,
    )

    assert payload["install"]["mode"] == "wheel"
    assert payload["install"]["operation"] == "rollback"
    assert payload["distribution"]["wheel_path"] == str(previous_wheel.resolve())
    assert calls[1]["command"][3] == "install"
    assert calls[1]["command"][-1] == f"thesis-format-tool[api] @ {previous_wheel.resolve().as_uri()}"


def test_install_local_app_surfaces_clear_error_on_install_failure(monkeypatch, tmp_path):
    def fake_run(command, *, cwd=None, capture_output=False, env=None):
        command = list(command)
        if command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            installer._venv_python(venv_dir).parent.mkdir(parents=True, exist_ok=True)
            installer._venv_python(venv_dir).write_text("", encoding="utf-8")
            return None
        raise installer.subprocess.CalledProcessError(2, command)

    monkeypatch.setattr(installer, "_run", fake_run)

    with pytest.raises(RuntimeError, match="Install failed while preparing the local editable package"):
        installer.install_local_app(
            python_executable=sys.executable,
            venv_dir=tmp_path / "venv",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "runtime",
            no_deps=True,
            skip_init=True,
        )


def test_install_local_app_surfaces_clear_error_on_invalid_init_json(monkeypatch, tmp_path):
    def fake_run(command, *, cwd=None, capture_output=False, env=None):
        command = list(command)
        if command[1:3] == ["-m", "venv"]:
            venv_dir = Path(command[-1])
            python_path = installer._venv_python(venv_dir)
            script_path = installer._venv_script(venv_dir, "article-local")
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("", encoding="utf-8")
            script_path.write_text("", encoding="utf-8")
            return None
        if command[0].endswith("article-local"):
            return type("Completed", (), {"stdout": "warning: noisy stdout"})()
        return None

    monkeypatch.setattr(installer, "_run", fake_run)

    with pytest.raises(RuntimeError, match="did not return valid JSON"):
        installer.install_local_app(
            python_executable=sys.executable,
            venv_dir=tmp_path / "venv",
            state_root=tmp_path / "state",
            runtime_root=tmp_path / "runtime",
            write_env=tmp_path / "article-local.env",
        )


def test_install_script_main_prints_json(capsys, monkeypatch):
    monkeypatch.setattr(
        installer,
        "install_local_app",
        lambda **_: {
            "status": "ok",
            "venv": {"article_local": "/tmp/article-local", "path": "/tmp/venv"},
            "install": {"skip_init": True},
            "quickstart": {"doctor": "/tmp/article-local doctor"},
            "init": None,
        },
    )

    exit_code = installer.main(["--no-deps", "--skip-init"])

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["install"]["skip_init"] is True
    assert payload["venv"]["article_local"]
    assert payload["quickstart"]["doctor"]
