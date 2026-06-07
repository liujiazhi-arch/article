from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Sequence


REQUIRED_RELEASE_ASSETS = [
    "article-local-windows.zip",
    "article-local-windows.zip.sha256",
]


def _run_gh(command: Sequence[str], *, timeout: float = 60.0) -> Any:
    completed = subprocess.run(
        ["gh", *command],
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )
    return json.loads(completed.stdout or "null")


def _run_git_config(key: str, *, timeout: float = 10.0) -> str:
    completed = subprocess.run(
        ["git", "config", "--get", key],
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )
    return completed.stdout.strip()


def _repo_from_remote_url(remote_url: str) -> str | None:
    value = remote_url.strip()
    patterns = [
        r"^git@github\.com:(?P<repo>[^/]+/[^/]+?)(?:\.git)?$",
        r"^https://github\.com/(?P<repo>[^/]+/[^/]+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/(?P<repo>[^/]+/[^/]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, value)
        if match:
            return match.group("repo")
    return None


def _infer_repo_from_origin() -> str | None:
    try:
        remote_url = _run_git_config("remote.origin.url")
    except subprocess.CalledProcessError:
        return None
    return _repo_from_remote_url(remote_url)


def _latest_ci_run(*, repo: str, branch: str) -> dict[str, Any]:
    runs = _run_gh(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            "CI",
            "--branch",
            branch,
            "--limit",
            "1",
            "--json",
            "databaseId,name,headBranch,status,conclusion",
        ]
    )
    if not runs:
        raise RuntimeError(f"No CI workflow runs found for {repo} branch {branch}")
    return dict(runs[0])


def _release_payload(*, repo: str, tag: str) -> dict[str, Any]:
    return dict(
        _run_gh(
            [
                "release",
                "view",
                tag,
                "--repo",
                repo,
                "--json",
                "tagName,isDraft,isPrerelease,assets",
            ]
        )
    )


def _asset_names(release: dict[str, Any]) -> list[str]:
    return sorted(str(asset.get("name", "")) for asset in release.get("assets", []) if asset.get("name"))


def check_github_release_status(
    *,
    repo: str | None = None,
    branch: str = "main",
    tag: str | None = None,
) -> dict[str, Any]:
    if not repo:
        repo = _infer_repo_from_origin()
    if not repo:
        raise RuntimeError(
            "GitHub repository is required. Pass --repo owner/name or configure git remote.origin.url."
        )
    if not tag:
        raise RuntimeError("GitHub release tag is required. Pass --tag vX.Y.Z.")

    latest_run = _latest_ci_run(repo=repo, branch=branch)
    release = _release_payload(repo=repo, tag=tag)
    assets = _asset_names(release)
    missing_assets = [name for name in REQUIRED_RELEASE_ASSETS if name not in assets]

    ci_ok = latest_run.get("status") == "completed" and latest_run.get("conclusion") == "success"
    release_ok = not release.get("isDraft") and not missing_assets
    status = "ok" if ci_ok and release_ok else "failed"

    return {
        "status": status,
        "repo": repo,
        "branch": branch,
        "tag": tag,
        "checks": {
            "latest_ci_run": latest_run,
            "release": {
                "tagName": release.get("tagName"),
                "isDraft": release.get("isDraft"),
                "isPrerelease": release.get("isPrerelease"),
            },
            "release_assets": {
                "required": list(REQUIRED_RELEASE_ASSETS),
                "present": assets,
                "missing": missing_assets,
            },
        },
        "next_steps": [] if status == "ok" else [
            "Inspect GitHub Actions CI and rerun failed jobs before publishing the beta.",
            "Confirm the GitHub Release contains article-local-windows.zip and article-local-windows.zip.sha256.",
        ],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="github_release_status.py")
    parser.add_argument("--repo", help="GitHub repository in owner/name form")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--tag", help="GitHub Release tag to inspect")
    parser.add_argument("--json-output", type=Path, help="Write the final JSON payload to this path")
    return parser


def _format_error(exc: Exception) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
        "next_steps": [
            "Pass --repo owner/name and --tag <release-tag> after pushing the branch and publishing a GitHub Release.",
            "Run gh auth status to confirm GitHub CLI authentication.",
        ],
    }
    if isinstance(exc, subprocess.CalledProcessError):
        payload["error"].update(
            {
                "command": [str(item) for item in (exc.cmd or [])],
                "returncode": exc.returncode,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            }
        )
    return payload


def _emit_payload(payload: dict[str, Any], *, json_output: Path | None = None) -> None:
    if json_output is not None:
        json_output = json_output.expanduser().resolve()
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = check_github_release_status(repo=args.repo, branch=args.branch, tag=args.tag)
    except Exception as exc:
        _emit_payload(_format_error(exc), json_output=args.json_output)
        return 1
    _emit_payload(payload, json_output=args.json_output)
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
