from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "fetch_public_docx_samples.py"


def _load_fetcher():
    spec = importlib.util.spec_from_file_location("fetch_public_docx_samples", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_public_docx_sample_catalog_covers_real_dirty_categories():
    fetcher = _load_fetcher()

    categories = {sample.category for sample in fetcher.PUBLIC_DOCX_SAMPLES}

    assert {
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
    } <= categories
    assert any(sample.audit_mode == "package-only" and sample.category == "nested_table" for sample in fetcher.PUBLIC_DOCX_SAMPLES)
    assert all(sample.url.startswith("https://raw.githubusercontent.com/") for sample in fetcher.PUBLIC_DOCX_SAMPLES)
    assert all(sample.source_relative_path.endswith(".docx") for sample in fetcher.PUBLIC_DOCX_SAMPLES)


def test_public_docx_sample_fetcher_invokes_intake_with_audit_mode(monkeypatch, tmp_path):
    fetcher = _load_fetcher()
    calls = []
    (tmp_path / "downloads").mkdir()

    for sample in fetcher.PUBLIC_DOCX_SAMPLES:
        (tmp_path / "downloads" / sample.filename).write_bytes(b"docx")

    def fake_run(command, **kwargs):
        calls.append([str(item) for item in command])
        return type("Completed", (), {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""})()

    monkeypatch.setattr(fetcher.subprocess, "run", fake_run)

    payload = fetcher.fetch_public_samples(
        download_dir=tmp_path / "downloads",
        output_dir=tmp_path / "sanitized",
        manifest_jsonl=tmp_path / "sanitized" / "manifest.jsonl",
        skip_download=True,
    )

    assert payload["status"] == "ok"
    assert len(calls) == len(fetcher.PUBLIC_DOCX_SAMPLES)
    for command, sample in zip(calls, fetcher.PUBLIC_DOCX_SAMPLES, strict=True):
        assert command[0] == sys.executable
        assert str(fetcher.INTAKE_SCRIPT) in command
        assert "--audit-mode" in command
        assert command[command.index("--audit-mode") + 1] == sample.audit_mode
        assert "--sample-id" in command
        assert command[command.index("--sample-id") + 1] == sample.sample_id


def test_public_docx_sample_fetcher_can_use_existing_source_checkout(monkeypatch, tmp_path):
    fetcher = _load_fetcher()
    calls = []
    source_dir = tmp_path / "source"

    for sample in fetcher.PUBLIC_DOCX_SAMPLES:
        source_path = source_dir / sample.source_relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"docx")

    def fail_download(*args, **kwargs):
        raise AssertionError("source-dir mode should not download")

    def fake_run(command, **kwargs):
        calls.append([str(item) for item in command])
        return type("Completed", (), {"returncode": 0, "stdout": '{"status":"ok"}', "stderr": ""})()

    monkeypatch.setattr(fetcher, "_download", fail_download)
    monkeypatch.setattr(fetcher.subprocess, "run", fake_run)

    payload = fetcher.fetch_public_samples(
        source_dir=source_dir,
        download_dir=tmp_path / "downloads",
        output_dir=tmp_path / "sanitized",
        manifest_jsonl=tmp_path / "sanitized" / "manifest.jsonl",
    )

    assert payload["status"] == "ok"
    for command, sample in zip(calls, fetcher.PUBLIC_DOCX_SAMPLES, strict=True):
        assert str(source_dir / sample.source_relative_path) in command
