from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


ET.register_namespace("cp", CORE_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("dcterms", DCTERMS_NS)
ET.register_namespace("w", W_NS)


def _safe_sample_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    if not normalized:
        raise ValueError("sample-id must contain at least one safe character")
    return normalized


def _validate_docx(path: Path) -> None:
    if path.suffix.lower() != ".docx":
        raise ValueError("source must be a .docx file")
    with zipfile.ZipFile(path, "r") as docx:
        names = set(docx.namelist())
    for required in ("[Content_Types].xml", "_rels/.rels", "word/document.xml"):
        if required not in names:
            raise ValueError(f"source is missing required DOCX part: {required}")


def _core_properties_xml(sample_id: str, category: str, source_app: str) -> bytes:
    root = ET.Element(f"{{{CORE_NS}}}coreProperties")
    values = {
        f"{{{DC_NS}}}title": sample_id,
        f"{{{DC_NS}}}creator": "sanitized",
        f"{{{CORE_NS}}}lastModifiedBy": "sanitized",
        f"{{{CORE_NS}}}category": category,
        f"{{{CORE_NS}}}contentStatus": f"sanitized real DOCX compatibility sample from {source_app}",
    }
    for tag, text in values.items():
        child = ET.SubElement(root, tag)
        child.text = text
    created = ET.SubElement(root, f"{{{DCTERMS_NS}}}created")
    created.set("{http://www.w3.org/2001/XMLSchema-instance}type", "dcterms:W3CDTF")
    created.text = "2026-01-01T00:00:00Z"
    modified = ET.SubElement(root, f"{{{DCTERMS_NS}}}modified")
    modified.set("{http://www.w3.org/2001/XMLSchema-instance}type", "dcterms:W3CDTF")
    modified.text = "2026-01-01T00:00:00Z"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _sanitize_word_xml(payload: bytes, *, sample_id: str) -> bytes:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return payload
    for elem in root.iter():
        for attr_name in list(elem.attrib):
            local_name = attr_name.rsplit("}", 1)[-1]
            if local_name in {"author", "initials", "date", "rsidR", "rsidRDefault", "rsidP", "rsidRPr"}:
                elem.attrib[attr_name] = "sanitized" if local_name in {"author", "initials"} else "2026-01-01T00:00:00Z"
        if elem.tag in {f"{{{W_NS}}}t", f"{{{W_NS}}}delText"} and elem.text:
            elem.text = elem.text.replace("tester", "sanitized").replace("测试者", "sanitized")
    try:
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    except RecursionError:
        return payload


def sanitize_docx(source_path: Path, output_path: Path, *, sample_id: str, category: str, source_app: str) -> None:
    _validate_docx(source_path)
    if output_path.exists():
        raise FileExistsError(f"sanitized sample already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".tmp.docx")
    try:
        with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                name = info.filename
                if name == "docProps/core.xml":
                    target.writestr(info, _core_properties_xml(sample_id, category, source_app))
                    continue
                payload = source.read(name)
                if name.startswith("word/") and name.endswith(".xml"):
                    payload = _sanitize_word_xml(payload, sample_id=sample_id)
                target.writestr(info, payload)
            if "docProps/core.xml" not in source.namelist():
                target.writestr("docProps/core.xml", _core_properties_xml(sample_id, category, source_app))
        temp_path.replace(output_path)
    finally:
        temp_path.unlink(missing_ok=True)


def append_manifest_entry(manifest_path: Path, entry: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sanitize and register a real DOCX compatibility sample.")
    parser.add_argument("source_docx")
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--source-app", required=True)
    parser.add_argument("--output-dir", default="tests/real_docx_samples/sanitized")
    parser.add_argument("--manifest-jsonl", default="tests/real_docx_samples/sanitized/manifest.jsonl")
    parser.add_argument(
        "--audit-mode",
        choices=("full", "package-only"),
        default="full",
        help="Use package-only for extreme public samples that are too slow for every audit regression.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        sample_id = _safe_sample_id(args.sample_id)
        source_path = Path(args.source_docx).expanduser().resolve()
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_path = output_dir / f"{sample_id}.docx"
        sanitize_docx(
            source_path,
            output_path,
            sample_id=sample_id,
            category=args.category,
            source_app=args.source_app,
        )
        entry = {
            "sample_id": sample_id,
            "category": args.category,
            "source_app": args.source_app,
            "audit_mode": args.audit_mode,
            "sanitized_path": str(output_path),
            "intake_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        append_manifest_entry(Path(args.manifest_jsonl).expanduser().resolve(), entry)
        print(json.dumps({"status": "ok", "sanitized_path": str(output_path), "manifest_entry": entry}, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
