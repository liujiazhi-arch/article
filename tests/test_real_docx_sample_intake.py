from __future__ import annotations

import json
from pathlib import Path
import subprocess
import zipfile

import audit_thesis
import pytest
import yaml

from article_api.uploads import validate_docx_package
from docx_sample_intake import sanitize_docx

from .compat_samples import COMPAT_SAMPLES, build_compat_sample


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "tests" / "real_docx_samples" / "manifest.yaml"
INTAKE_SCRIPT = PROJECT_ROOT / "scripts" / "docx_sample_intake.py"
SANITIZED_MANIFEST_JSONL = PROJECT_ROOT / "tests" / "real_docx_samples" / "sanitized" / "manifest.jsonl"


def test_real_docx_sample_policy_keeps_private_binaries_out_of_git():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        "tests/real_docx_samples/private/",
        "tests/real_docx_samples/sanitized/*.docx",
        "tests/real_docx_samples/sanitized/*.zip",
        "tests/real_docx_samples/sanitized/manifest.jsonl",
    ):
        assert pattern in gitignore

    assert MANIFEST_PATH.exists()
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["policy"]["private_samples_ignored"] is True
    assert manifest["policy"]["commit_sanitized_only_with_review"] is True
    assert {item["id"] for item in manifest["required_categories"]} == {
        "wps",
        "word",
        "toc_field",
        "footnote",
        "comment",
        "revision",
        "floating_image",
        "formula",
        "nested_table",
        "section_break",
    }


def test_docx_sample_intake_sanitizes_metadata_and_records_manifest_entry(tmp_path):
    source = build_compat_sample(
        sample=next(item for item in COMPAT_SAMPLES if item.id == "comments"),
        output_dir=tmp_path / "source",
    )
    output_dir = tmp_path / "sanitized"
    manifest_path = tmp_path / "manifest.jsonl"

    result = subprocess.run(
        [
            "python3",
            str(INTAKE_SCRIPT),
            str(source),
            "--sample-id",
            "real-comment-case",
            "--category",
            "comment",
            "--source-app",
            "Word",
            "--output-dir",
            str(output_dir),
            "--manifest-jsonl",
            str(manifest_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(result.stdout)
    sanitized_path = Path(payload["sanitized_path"])

    assert payload["status"] == "ok"
    assert sanitized_path.exists()
    assert sanitized_path.name == "real-comment-case.docx"
    assert payload["manifest_entry"]["category"] == "comment"
    assert payload["manifest_entry"]["source_app"] == "Word"
    assert payload["manifest_entry"]["audit_mode"] == "full"
    assert manifest_path.exists()
    entry = json.loads(manifest_path.read_text(encoding="utf-8").strip())
    assert entry["sample_id"] == "real-comment-case"
    assert entry["sanitized_path"] == str(sanitized_path)

    with zipfile.ZipFile(sanitized_path, "r") as docx_file:
        names = set(docx_file.namelist())
        assert "docProps/core.xml" in names
        all_xml = "\n".join(
            docx_file.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith(".xml")
        )

    assert source.name not in all_xml
    assert "tester" not in all_xml
    assert "real-comment-case" in all_xml

    second = subprocess.run(
        [
            "python3",
            str(INTAKE_SCRIPT),
            str(source),
            "--sample-id",
            "real-comment-case",
            "--category",
            "comment",
            "--source-app",
            "Word",
            "--output-dir",
            str(output_dir),
            "--manifest-jsonl",
            str(manifest_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert second.returncode != 0
    assert "already exists" in second.stderr


def test_docx_sample_intake_keeps_deep_word_xml_from_blocking_intake(tmp_path):
    source_path = tmp_path / "deep-word-xml.docx"
    output_path = tmp_path / "sanitized" / "deep-word-xml.docx"
    nested_open = "".join(f"<w:tbl><w:tr><w:tc><w:p><w:r><w:t>{index}</w:t></w:r></w:p>" for index in range(1200))
    nested_close = "</w:tc></w:tr></w:tbl>" * 1200
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{nested_open}{nested_close}</w:body></w:document>"
    )

    with zipfile.ZipFile(source_path, "w", zipfile.ZIP_DEFLATED) as docx_file:
        docx_file.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        docx_file.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )
        docx_file.writestr("word/document.xml", document_xml)

    sanitize_docx(
        source_path,
        output_path,
        sample_id="deep-word-xml",
        category="nested_table",
        source_app="generated",
    )

    assert Path(validate_docx_package(output_path)) == output_path.resolve()
    with zipfile.ZipFile(output_path, "r") as docx_file:
        assert "docProps/core.xml" in set(docx_file.namelist())
        assert docx_file.read("word/document.xml").decode("utf-8") == document_xml


def test_docx_sample_intake_records_package_only_audit_mode(tmp_path):
    source = build_compat_sample(
        sample=next(item for item in COMPAT_SAMPLES if item.id == "nested_table"),
        output_dir=tmp_path / "source",
    )
    output_dir = tmp_path / "sanitized"
    manifest_path = tmp_path / "manifest.jsonl"

    result = subprocess.run(
        [
            "python3",
            str(INTAKE_SCRIPT),
            str(source),
            "--sample-id",
            "real-deep-table-case",
            "--category",
            "nested_table",
            "--source-app",
            "public",
            "--audit-mode",
            "package-only",
            "--output-dir",
            str(output_dir),
            "--manifest-jsonl",
            str(manifest_path),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    payload = json.loads(result.stdout)
    entry = json.loads(manifest_path.read_text(encoding="utf-8").strip())
    assert payload["manifest_entry"]["audit_mode"] == "package-only"
    assert entry["audit_mode"] == "package-only"


def _local_sanitized_manifest_entries() -> list[dict[str, str]]:
    if not SANITIZED_MANIFEST_JSONL.exists():
        return []
    entries = []
    for line in SANITIZED_MANIFEST_JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def test_local_sanitized_real_docx_samples_run_package_validation_and_audit():
    entries = _local_sanitized_manifest_entries()
    if not entries:
        pytest.skip("No local sanitized real DOCX samples registered yet; use scripts/docx_sample_intake.py.")

    for entry in entries:
        sample_path = Path(entry["sanitized_path"])
        assert sample_path.exists(), entry
        assert Path(validate_docx_package(sample_path)) == sample_path.resolve()

        if entry.get("audit_mode", "full") == "package-only":
            continue

        results, score, _report, runtime = audit_thesis.audit_docx_with_runtime(str(sample_path), profile_path="lnu")

        assert runtime.profile_id == "lnu-checker-2026"
        assert len(results) == len(runtime.rule_definitions)
        assert isinstance(score, int)
