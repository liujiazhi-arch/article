from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import xml.etree.ElementTree as ET

import fix_output_parts


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": W_NS}


def _set_attr(elem, attr, value):
    elem.set(f"{{{W_NS}}}{attr}", value)


def test_build_settings_with_update_fields_creates_flag():
    payload = fix_output_parts.build_settings_with_update_fields(
        None,
        w_ns=W_NS,
        nsmap=NSMAP,
        set_attr=_set_attr,
    )

    root = ET.fromstring(payload)
    update_fields = root.find("w:updateFields", NSMAP)
    assert update_fields is not None
    assert update_fields.get(f"{{{W_NS}}}val") == "true"


def test_build_updated_parts_includes_settings_document_and_styles(tmp_path: Path):
    word_dir = tmp_path / "word"
    word_dir.mkdir()
    (word_dir / "settings.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
        encoding="utf-8",
    )
    (word_dir / "styles.xml").write_bytes(b"<styles/>")

    document_root = ET.Element(f"{{{W_NS}}}document")
    scope_flags = SimpleNamespace(page=True)
    runtime = SimpleNamespace()
    ctx = SimpleNamespace(
        temp_dir=str(tmp_path),
        document_root=document_root,
        cfg={},
        runtime=runtime,
        scope_flags=scope_flags,
    )

    def footer_builder(_temp_dir, _document_root, _cfg, runtime=None):
        assert runtime is runtime
        return {"word/footer1.xml": b"<footer/>"}

    def settings_builder(existing_settings_xml):
        assert existing_settings_xml is not None
        return b"<settings/>"

    updated = fix_output_parts.build_updated_parts(
        ctx=ctx,
        toc_parts={"word/settings.xml": b"placeholder"},
        footer_builder=footer_builder,
        settings_builder=settings_builder,
    )

    assert updated["word/footer1.xml"] == b"<footer/>"
    assert updated["word/settings.xml"] == b"<settings/>"
    assert updated["word/styles.xml"] == b"<styles/>"
    assert updated["word/document.xml"].startswith(b"<?xml")
