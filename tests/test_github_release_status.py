from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "github_release_status.py"


def _load_github_release_status():
    spec = importlib.util.spec_from_file_location("github_release_status", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_github_release_status_checks_actions_and_release_assets(monkeypatch):
    github_release_status = _load_github_release_status()
    calls: list[list[str]] = []

    def fake_run(command, *, capture_output=True, text=True, check=True, timeout=None):
        command = [str(item) for item in command]
        calls.append(command)
        if command[:3] == ["gh", "run", "list"]:
            return type(
                "Completed",
                (),
                {
                    "stdout": json.dumps(
                        [
                            {
                                "databaseId": 123,
                                "name": "CI",
                                "headBranch": "main",
                                "status": "completed",
                                "conclusion": "success",
                            }
                        ]
                    ),
                    "stderr": "",
                },
            )()
        if command[:3] == ["gh", "release", "view"]:
            return type(
                "Completed",
                (),
                {
                    "stdout": json.dumps(
                        {
                            "tagName": "v0.1.0",
                            "isDraft": False,
                            "isPrerelease": True,
                            "assets": [
                                {"name": "lnu-thesis-local-windows.zip", "size": 100},
                                {"name": "lnu-thesis-local-windows.zip.sha256", "size": 96},
                            ],
                        }
                    ),
                    "stderr": "",
                },
            )()
        raise AssertionError(command)

    monkeypatch.setattr(github_release_status.subprocess, "run", fake_run)

    payload = github_release_status.check_github_release_status(
        repo="owner/article",
        branch="main",
        tag="v0.1.0",
    )

    assert payload["status"] == "ok"
    assert payload["checks"]["latest_ci_run"]["conclusion"] == "success"
    assert payload["checks"]["release_assets"]["required"] == [
        "lnu-thesis-local-windows.zip",
        "lnu-thesis-local-windows.zip.sha256",
    ]
    assert payload["checks"]["release_assets"]["missing"] == []
    assert calls == [
        [
            "gh",
            "run",
            "list",
            "--repo",
            "owner/article",
            "--workflow",
            "CI",
            "--branch",
            "main",
            "--limit",
            "1",
            "--json",
            "databaseId,name,headBranch,status,conclusion",
        ],
        [
            "gh",
            "release",
            "view",
            "v0.1.0",
            "--repo",
            "owner/article",
            "--json",
            "tagName,isDraft,isPrerelease,assets",
        ],
    ]


def test_github_release_status_fails_when_assets_are_missing(monkeypatch):
    github_release_status = _load_github_release_status()

    def fake_run(command, *, capture_output=True, text=True, check=True, timeout=None):
        command = [str(item) for item in command]
        if command[:3] == ["gh", "run", "list"]:
            return type(
                "Completed",
                (),
                {"stdout": json.dumps([{"status": "completed", "conclusion": "success"}]), "stderr": ""},
            )()
        return type(
            "Completed",
            (),
            {"stdout": json.dumps({"tagName": "v0.1.0", "assets": [{"name": "lnu-thesis-local-windows.zip"}]}), "stderr": ""},
        )()

    monkeypatch.setattr(github_release_status.subprocess, "run", fake_run)

    payload = github_release_status.check_github_release_status(
        repo="owner/article",
        branch="main",
        tag="v0.1.0",
    )

    assert payload["status"] == "failed"
    assert payload["checks"]["release_assets"]["missing"] == ["lnu-thesis-local-windows.zip.sha256"]


def test_github_release_status_cli_reports_json_error(monkeypatch, capsys):
    github_release_status = _load_github_release_status()

    def fake_check(**kwargs):
        raise RuntimeError("GitHub repository is required")

    monkeypatch.setattr(github_release_status, "check_github_release_status", fake_check)

    exit_code = github_release_status.main([])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["error"]["type"] == "RuntimeError"
    assert "GitHub repository is required" in payload["error"]["message"]


def test_github_release_status_cli_writes_json_output(monkeypatch, capsys, tmp_path):
    github_release_status = _load_github_release_status()
    output_path = tmp_path / "github-status.json"

    monkeypatch.setattr(
        github_release_status,
        "check_github_release_status",
        lambda **kwargs: {"status": "ok", "repo": kwargs["repo"], "tag": kwargs["tag"]},
    )

    exit_code = github_release_status.main(
        [
            "--repo",
            "owner/article",
            "--tag",
            "v0.1.0",
            "--json-output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert written == payload


def test_github_release_status_can_infer_repo_from_github_remote(monkeypatch):
    github_release_status = _load_github_release_status()
    calls: list[list[str]] = []

    def fake_run(command, *, capture_output=True, text=True, check=True, timeout=None):
        command = [str(item) for item in command]
        calls.append(command)
        if command[:3] == ["git", "config", "--get"]:
            return type("Completed", (), {"stdout": "git@github.com:owner/article.git\n", "stderr": ""})()
        if command[:3] == ["gh", "run", "list"]:
            return type(
                "Completed",
                (),
                {"stdout": json.dumps([{"status": "completed", "conclusion": "success"}]), "stderr": ""},
            )()
        if command[:3] == ["gh", "release", "view"]:
            return type(
                "Completed",
                (),
                {
                    "stdout": json.dumps(
                        {
                            "tagName": "v0.1.0",
                            "isDraft": False,
                            "assets": [
                                {"name": "lnu-thesis-local-windows.zip"},
                                {"name": "lnu-thesis-local-windows.zip.sha256"},
                            ],
                        }
                    ),
                    "stderr": "",
                },
            )()
        raise AssertionError(command)

    monkeypatch.setattr(github_release_status.subprocess, "run", fake_run)

    payload = github_release_status.check_github_release_status(tag="v0.1.0")

    assert payload["status"] == "ok"
    assert payload["repo"] == "owner/article"
    assert ["git", "config", "--get", "remote.origin.url"] in calls


def test_github_release_status_reports_missing_repo_and_remote(monkeypatch):
    github_release_status = _load_github_release_status()

    def fake_run(command, *, capture_output=True, text=True, check=True, timeout=None):
        command = [str(item) for item in command]
        if command[:3] == ["git", "config", "--get"]:
            raise subprocess.CalledProcessError(1, command, output="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(github_release_status.subprocess, "run", fake_run)

    try:
        github_release_status.check_github_release_status(tag="v0.1.0")
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("missing repo should fail")

    assert "GitHub repository is required" in message
    assert "remote.origin.url" in message
