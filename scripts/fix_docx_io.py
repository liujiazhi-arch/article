import copy
import os
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from docx import Document


REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _register_header_rels(temp_dir):
    rels_path = os.path.join(temp_dir, "word", "_rels", "document.xml.rels")
    content_types_path = os.path.join(temp_dir, "[Content_Types].xml")
    if not os.path.exists(rels_path) or not os.path.exists(content_types_path):
        return

    rels_root = ET.parse(rels_path).getroot()
    has_header_rel = any(
        rel.get("Type") in (f"{REL_NS}/header", f"{PACKAGE_REL_NS}/header")
        for rel in rels_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
    )
    if not has_header_rel:
        relationship = ET.SubElement(rels_root, f"{{{PACKAGE_REL_NS}}}Relationship")
        relationship.set("Id", "rId_hdr1")
        relationship.set("Type", f"{REL_NS}/header")
        relationship.set("Target", "header1.xml")
        ET.ElementTree(rels_root).write(rels_path, encoding="utf-8", xml_declaration=True)

    content_types_root = ET.parse(content_types_path).getroot()
    has_header_override = any(
        override.get("PartName") == "/word/header1.xml"
        for override in content_types_root.findall(f"{{{CONTENT_TYPES_NS}}}Override")
    )
    if not has_header_override:
        override = ET.SubElement(content_types_root, f"{{{CONTENT_TYPES_NS}}}Override")
        override.set("PartName", "/word/header1.xml")
        override.set(
            "ContentType",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
        )
        ET.ElementTree(content_types_root).write(content_types_path, encoding="utf-8", xml_declaration=True)


def _merge_styles_xml(template_styles_path, doc_styles_path):
    wns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    w = "{%s}" % wns

    try:
        tmpl_root = ET.parse(template_styles_path).getroot()
        doc_root = ET.parse(doc_styles_path).getroot()
    except Exception:
        return

    doc_styles_by_name = {}
    for style_elem in doc_root.findall(f"{w}style"):
        name_elem = style_elem.find(f"{w}name")
        if name_elem is not None:
            style_name = name_elem.get(f"{w}val", "").lower().strip()
            doc_styles_by_name[style_name] = style_elem

    for tmpl_style in tmpl_root.findall(f"{w}style"):
        tmpl_name_elem = tmpl_style.find(f"{w}name")
        if tmpl_name_elem is None:
            continue
        tmpl_name = tmpl_name_elem.get(f"{w}val", "").lower().strip()
        if not tmpl_name:
            continue

        doc_style = doc_styles_by_name.get(tmpl_name)
        if doc_style is not None:
            for tag in (f"{w}pPr", f"{w}rPr"):
                tmpl_block = tmpl_style.find(tag)
                doc_block = doc_style.find(tag)
                if tmpl_block is None:
                    continue
                if doc_block is not None:
                    doc_style.remove(doc_block)
                name_idx = list(doc_style).index(doc_style.find(f"{w}name"))
                doc_style.insert(name_idx + 1, copy.deepcopy(tmpl_block))
        else:
            tmpl_sid = tmpl_style.get(f"{w}styleId", "")
            if tmpl_sid and tmpl_sid in {style.get(f"{w}styleId", "") for style in doc_root.findall(f"{w}style")}:
                tmpl_style.set(f"{w}styleId", "tmpl_" + tmpl_sid)
            doc_root.append(tmpl_style)

    tmpl_defaults = tmpl_root.find(f"{w}docDefaults")
    if tmpl_defaults is not None:
        doc_defaults = doc_root.find(f"{w}docDefaults")
        if doc_defaults is not None:
            doc_root.remove(doc_defaults)
        doc_root.insert(0, tmpl_defaults)

    ET.ElementTree(doc_root).write(doc_styles_path, encoding="utf-8", xml_declaration=True)


def inject_template_components(temp_dir, profile_id):
    template_dir = os.path.join(TOOL_ROOT, "config", "templates", profile_id)
    if not profile_id or not os.path.isdir(template_dir):
        return

    copied_header1 = False
    components = [
        ("numbering.xml", os.path.join("word", "numbering.xml")),
        ("header1.xml", os.path.join("word", "header1.xml")),
        ("header2.xml", os.path.join("word", "header2.xml")),
    ]

    styles_tpl = os.path.join(template_dir, "styles.xml")
    styles_doc = os.path.join(temp_dir, "word", "styles.xml")
    if os.path.isfile(styles_tpl):
        os.makedirs(os.path.dirname(styles_doc), exist_ok=True)
        if os.path.isfile(styles_doc):
            _merge_styles_xml(styles_tpl, styles_doc)
        else:
            shutil.copyfile(styles_tpl, styles_doc)

    for source_name, target_relpath in components:
        try:
            source_path = os.path.join(template_dir, source_name)
            if not os.path.isfile(source_path):
                continue
            target_path = os.path.join(temp_dir, target_relpath)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copyfile(source_path, target_path)
            if source_name == "header1.xml":
                copied_header1 = True
        except Exception:
            continue

    if copied_header1:
        _register_header_rels(temp_dir)


def _validate_written_docx(path: str) -> None:
    try:
        with zipfile.ZipFile(path, "r") as zip_handle:
            invalid_member = zip_handle.testzip()
            if invalid_member is not None:
                raise RuntimeError(f"zip member is corrupted: {invalid_member}")
    except Exception as exc:
        raise RuntimeError(f"输出文件 zip 校验失败: {path}") from exc

    try:
        Document(path)
    except Exception as exc:
        raise RuntimeError(f"输出文件无法被 python-docx 重新打开: {path}") from exc


def write_docx_atomically(input_path: str, output_path: str, updated_parts: dict[str, bytes]) -> None:
    output_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    temp_output_path = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix=".thesis_fix_tmp_",
            suffix=".docx",
            dir=output_dir,
            delete=False,
        ) as temp_handle:
            temp_output_path = temp_handle.name

        with zipfile.ZipFile(input_path, "r") as source_zip, zipfile.ZipFile(temp_output_path, "w", zipfile.ZIP_DEFLATED) as target_zip:
            written_files = set()
            for item in source_zip.infolist():
                if item.filename in updated_parts:
                    target_zip.writestr(item, updated_parts[item.filename])
                    written_files.add(item.filename)
                else:
                    target_zip.writestr(item, source_zip.read(item.filename))
            for filename, content in updated_parts.items():
                if filename not in written_files:
                    target_zip.writestr(filename, content)

        _validate_written_docx(temp_output_path)
        os.replace(temp_output_path, output_path)
    except Exception:
        if temp_output_path and os.path.exists(temp_output_path):
            os.remove(temp_output_path)
        raise
