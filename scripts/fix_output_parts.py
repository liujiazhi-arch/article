from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from ooxml_namespaces import declare_ignorable_namespaces


def build_settings_with_update_fields(settings_xml=None, *, w_ns: str, nsmap: dict, set_attr) -> bytes:
    if settings_xml:
        try:
            settings_root = ET.fromstring(settings_xml)
        except ET.ParseError:
            settings_root = ET.Element(f"{{{w_ns}}}settings")
    else:
        settings_root = ET.Element(f"{{{w_ns}}}settings")

    update_fields = settings_root.find("w:updateFields", nsmap)
    if update_fields is None:
        update_fields = ET.SubElement(settings_root, f"{{{w_ns}}}updateFields")
    set_attr(update_fields, "val", "true")
    return ET.tostring(settings_root, encoding="utf-8", xml_declaration=True)


def build_updated_parts(
    *,
    ctx,
    toc_parts: dict[str, bytes],
    cover_parts: dict[str, bytes] | None = None,
    footer_builder,
    settings_builder,
) -> dict[str, bytes]:
    normalized_toc_parts = dict(toc_parts)

    if "word/settings.xml" in normalized_toc_parts and ctx.temp_dir is not None:
        settings_path = os.path.join(ctx.temp_dir, "word", "settings.xml")
        existing_settings_xml = None
        if os.path.exists(settings_path):
            with open(settings_path, "rb") as handle:
                existing_settings_xml = handle.read()
        normalized_toc_parts["word/settings.xml"] = settings_builder(existing_settings_xml)

    updated_parts = dict(normalized_toc_parts)
    for name, payload in (cover_parts or {}).items():
        updated_parts.setdefault(name, payload)
    if ctx.scope_flags.page and ctx.temp_dir is not None:
        updated_parts.update(footer_builder(ctx.temp_dir, ctx.document_root, ctx.cfg, runtime=ctx.runtime))
    declare_ignorable_namespaces(ctx.document_root)
    updated_parts["word/document.xml"] = ET.tostring(ctx.document_root, encoding="utf-8", xml_declaration=True)

    merged_styles_path = os.path.join(ctx.temp_dir, "word", "styles.xml") if ctx.temp_dir is not None else None
    if merged_styles_path and os.path.isfile(merged_styles_path):
        with open(merged_styles_path, "rb") as handle:
            updated_parts["word/styles.xml"] = handle.read()

    return updated_parts
