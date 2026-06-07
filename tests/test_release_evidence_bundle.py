from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "release_evidence_bundle.py"


def _load_release_evidence_bundle():
    spec = importlib.util.spec_from_file_location("release_evidence_bundle", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_evidence_bundle_includes_only_named_json_and_markdown_evidence(tmp_path):
    release_evidence_bundle = _load_release_evidence_bundle()
    github_status = tmp_path / "article-github-status.json"
    release_smoke = tmp_path / "article-release-smoke.json"
    windows_bundle_smoke = tmp_path / "windows-bundle-smoke.json"
    windows_report = tmp_path / "windows-smoke-report.md"
    output_zip = tmp_path / "release-evidence.zip"
    github_status.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    release_smoke.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    windows_bundle_smoke.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    windows_report.write_text("# Windows smoke\n- 发布结论: 通过\n", encoding="utf-8")

    payload = release_evidence_bundle.build_release_evidence_bundle(
        output_zip=output_zip,
        evidence_paths=[
            github_status,
            release_smoke,
            windows_bundle_smoke,
            windows_report,
        ],
    )

    assert payload["status"] == "ok"
    assert payload["entry_count"] == 5
    with zipfile.ZipFile(output_zip) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert names == {
        "manifest.json",
        "evidence/article-github-status.json",
        "evidence/article-release-smoke.json",
        "evidence/windows-bundle-smoke.json",
        "evidence/windows-smoke-report.md",
    }
    assert manifest["kind"] == "article-local-release-evidence"
    assert manifest["privacy"]["includes_documents"] is False
    assert manifest["privacy"]["includes_secrets"] is False
    assert [item["archive_name"] for item in manifest["files"]] == sorted(names - {"manifest.json"})


def test_release_evidence_bundle_rejects_document_or_secret_inputs(tmp_path):
    release_evidence_bundle = _load_release_evidence_bundle()
    document = tmp_path / "论文.docx"
    env_file = tmp_path / ".env"
    document.write_bytes(b"docx")
    env_file.write_text("API_KEY=secret", encoding="utf-8")

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        release_evidence_bundle.build_release_evidence_bundle(
            output_zip=tmp_path / "release-evidence.zip",
            evidence_paths=[document],
        )

    with pytest.raises(RuntimeError, match="privacy-sensitive"):
        release_evidence_bundle.build_release_evidence_bundle(
            output_zip=tmp_path / "release-evidence.zip",
            evidence_paths=[env_file],
        )


def test_release_evidence_bundle_cli_writes_json_payload(capsys, tmp_path):
    release_evidence_bundle = _load_release_evidence_bundle()
    evidence = tmp_path / "article-github-status.json"
    output_zip = tmp_path / "release-evidence.zip"
    evidence.write_text(json.dumps({"status": "failed"}), encoding="utf-8")

    exit_code = release_evidence_bundle.main(
        [
            "--output-zip",
            str(output_zip),
            "--evidence",
            str(evidence),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert output_zip.exists()
