from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTAKE_SCRIPT = PROJECT_ROOT / "scripts" / "docx_sample_intake.py"
DEFAULT_DOWNLOAD_DIR = PROJECT_ROOT / "tests" / "real_docx_samples" / "public_downloads"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tests" / "real_docx_samples" / "sanitized"
DEFAULT_MANIFEST_JSONL = DEFAULT_OUTPUT_DIR / "manifest.jsonl"


@dataclass(frozen=True)
class PublicDocxSample:
    sample_id: str
    category: str
    source_app: str
    url: str
    source_relative_path: str
    audit_mode: str = "full"

    @property
    def filename(self) -> str:
        return f"{self.sample_id}.docx"


PUBLIC_DOCX_SAMPLES: tuple[PublicDocxSample, ...] = (
    PublicDocxSample(
        sample_id="public-poi-footnotes",
        category="footnote",
        source_app="Apache POI public test-data",
        url="https://raw.githubusercontent.com/apache/poi/trunk/test-data/document/footnotes.docx",
        source_relative_path="poi/test-data/document/footnotes.docx",
    ),
    PublicDocxSample(
        sample_id="public-poi-comment",
        category="comment",
        source_app="Apache POI public test-data",
        url="https://raw.githubusercontent.com/apache/poi/trunk/test-data/document/comment.docx",
        source_relative_path="poi/test-data/document/comment.docx",
    ),
    PublicDocxSample(
        sample_id="public-poi-delins",
        category="revision",
        source_app="Apache POI public test-data",
        url="https://raw.githubusercontent.com/apache/poi/trunk/test-data/document/delins.docx",
        source_relative_path="poi/test-data/document/delins.docx",
    ),
    PublicDocxSample(
        sample_id="public-poi-fieldcodes",
        category="word",
        source_app="Apache POI public test-data",
        url="https://raw.githubusercontent.com/apache/poi/trunk/test-data/document/FieldCodes.docx",
        source_relative_path="poi/test-data/document/FieldCodes.docx",
    ),
    PublicDocxSample(
        sample_id="public-poi-various-pictures",
        category="floating_image",
        source_app="Apache POI public test-data",
        url="https://raw.githubusercontent.com/apache/poi/trunk/test-data/document/VariousPictures.docx",
        source_relative_path="poi/test-data/document/VariousPictures.docx",
    ),
    PublicDocxSample(
        sample_id="public-docx4j-2010-sample1",
        category="formula",
        source_app="docx4j public sample-docs",
        url="https://raw.githubusercontent.com/plutext/docx4j/master/docx4j-samples-docx4j/sample-docs/2010/2010-sample1.docx",
        source_relative_path="docx4j/docx4j-samples-docx4j/sample-docs/2010/2010-sample1.docx",
    ),
    PublicDocxSample(
        sample_id="public-poi-deep-table-cell",
        category="nested_table",
        source_app="Apache POI public test-data",
        url="https://raw.githubusercontent.com/apache/poi/trunk/test-data/document/deep-table-cell.docx",
        source_relative_path="poi/test-data/document/deep-table-cell.docx",
        audit_mode="package-only",
    ),
    PublicDocxSample(
        sample_id="public-poi-with-tabs",
        category="section_break",
        source_app="Apache POI public test-data",
        url="https://raw.githubusercontent.com/apache/poi/trunk/test-data/document/WithTabs.docx",
        source_relative_path="poi/test-data/document/WithTabs.docx",
    ),
    PublicDocxSample(
        sample_id="public-docx4j-toc",
        category="toc_field",
        source_app="docx4j public sample-docs",
        url="https://raw.githubusercontent.com/plutext/docx4j/master/docx4j-samples-docx4j/sample-docs/toc.docx",
        source_relative_path="docx4j/docx4j-samples-docx4j/sample-docs/toc.docx",
    ),
    PublicDocxSample(
        sample_id="public-docx4j-drawingml-wps",
        category="wps",
        source_app="docx4j public sample-docs",
        url="https://raw.githubusercontent.com/plutext/docx4j/master/docx4j-samples-docx4j/sample-docs/2010/DrawingML_GraphicData_wps.docx",
        source_relative_path="docx4j/docx4j-samples-docx4j/sample-docs/2010/DrawingML_GraphicData_wps.docx",
    ),
)


def _download(url: str, target_path: Path, *, timeout: float) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as response, target_path.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _intake_command(
    sample: PublicDocxSample,
    source_path: Path,
    *,
    output_dir: Path,
    manifest_jsonl: Path,
) -> list[str]:
    return [
        sys.executable,
        str(INTAKE_SCRIPT),
        str(source_path),
        "--sample-id",
        sample.sample_id,
        "--category",
        sample.category,
        "--source-app",
        sample.source_app,
        "--audit-mode",
        sample.audit_mode,
        "--output-dir",
        str(output_dir),
        "--manifest-jsonl",
        str(manifest_jsonl),
    ]


def fetch_public_samples(
    *,
    download_dir: Path = DEFAULT_DOWNLOAD_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_jsonl: Path = DEFAULT_MANIFEST_JSONL,
    source_dir: Path | None = None,
    timeout_seconds: float = 60.0,
    skip_download: bool = False,
    overwrite_downloads: bool = False,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for sample in PUBLIC_DOCX_SAMPLES:
        source_path = source_dir / sample.source_relative_path if source_dir is not None else download_dir / sample.filename
        if source_dir is None and not skip_download and (overwrite_downloads or not source_path.exists()):
            _download(sample.url, source_path, timeout=timeout_seconds)
        if not source_path.exists():
            raise FileNotFoundError(f"Public sample source is missing: {source_path}")
        result = subprocess.run(
            _intake_command(sample, source_path, output_dir=output_dir, manifest_jsonl=manifest_jsonl),
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0 and "already exists" not in result.stderr:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        items.append(
            {
                "sample_id": sample.sample_id,
                "category": sample.category,
                "audit_mode": sample.audit_mode,
                "source_path": str(source_path),
                "status": "already_exists" if result.returncode != 0 else "intake_ok",
            }
        )
    return {
        "status": "ok",
        "download_dir": str(download_dir),
        "output_dir": str(output_dir),
        "manifest_jsonl": str(manifest_jsonl),
        "items": items,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch public DOCX compatibility samples and register sanitized copies.")
    parser.add_argument("--download-dir", default=str(DEFAULT_DOWNLOAD_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--manifest-jsonl", default=str(DEFAULT_MANIFEST_JSONL))
    parser.add_argument("--source-dir", help="Use an existing public sample checkout instead of downloading raw URLs")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--overwrite-downloads", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = fetch_public_samples(
            download_dir=Path(args.download_dir).expanduser().resolve(),
            output_dir=Path(args.output_dir).expanduser().resolve(),
            manifest_jsonl=Path(args.manifest_jsonl).expanduser().resolve(),
            source_dir=Path(args.source_dir).expanduser().resolve() if args.source_dir else None,
            timeout_seconds=float(args.timeout_seconds),
            skip_download=bool(args.skip_download),
            overwrite_downloads=bool(args.overwrite_downloads),
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
