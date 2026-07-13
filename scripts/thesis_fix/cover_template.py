from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
import os
import posixpath
import xml.etree.ElementTree as ET

from ooxml_namespaces import serialize_opc_root
from thesis_resources import config_path


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
NS = {"w": W_NS, "r": R_NS, "wp": WP_NS, "a": A_NS}
IMAGE_REL_TYPE = f"{R_NS}/image"
EMU_PER_INCH = 914400
COVER_FIELD_NAMES = (
    "thesis_title",
    "college",
    "major",
    "student_name",
    "advisor",
    "completion_date",
)
FIELD_LABELS = (
    ("题    目：", "thesis_title"),
    ("学    院：", "college"),
    ("专    业：", "major"),
    ("姓    名：", "student_name"),
    ("指导教师：", "advisor"),
    ("完成日期：", "completion_date"),
)
BOUNDARY_MODULES = {"abstract_cn_title", "abstract_en_title", "toc_title", "body_heading"}
COVER_DRAWING_ASSETS = {
    "LNU Cover Wordmark": "wordmark.jpeg",
    "LNU Cover Emblem": "emblem.png",
}
IMAGE_CONTENT_TYPES = {"jpeg": "image/jpeg", "png": "image/png"}

for prefix, uri in (("w", W_NS), ("r", R_NS), ("wp", WP_NS), ("a", A_NS), ("pic", PIC_NS)):
    ET.register_namespace(prefix, uri)


class CoverReplacementError(ValueError):
    """Raised before output when an existing cover cannot be isolated safely."""


@dataclass(frozen=True)
class CoverPlan:
    body: ET.Element
    targets: tuple[ET.Element, ...]
    boundary: ET.Element


@dataclass(frozen=True)
class CoverReplacement:
    status: str
    removed_top_level_elements: int
    updated_parts: dict[str, bytes]


def _q(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def normalize_cover_fields(fields) -> dict[str, str] | None:
    if fields is None:
        return None
    if not isinstance(fields, Mapping):
        raise ValueError("cover_fields 必须是六项字段映射")
    unexpected = sorted(set(fields) - set(COVER_FIELD_NAMES))
    if unexpected:
        raise ValueError(f"cover_fields 包含未知字段: {', '.join(unexpected)}")
    return {name: _required_field(fields, name) for name in COVER_FIELD_NAMES}


def _required_field(fields: Mapping, name: str) -> str:
    value = fields.get(name)
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValueError(f"cover_fields.{name} 不能为空")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError(f"cover_fields.{name} 不能包含换行或控制字符")
    return normalized


def _child_nodes(child: ET.Element, node_by_id: dict[int, object]) -> list[object]:
    paragraphs = child.findall(".//w:p", NS)
    if child.tag == _q(W_NS, "p"):
        paragraphs.insert(0, child)
    nodes = [node_by_id.get(id(paragraph)) for paragraph in paragraphs]
    if not paragraphs or any(node is None for node in nodes):
        raise CoverReplacementError("封面边界不明确，已拒绝替换")
    return nodes


def _first_boundary_module(nodes: list[object]) -> str | None:
    first = next((node for node in nodes if node.text.strip()), nodes[0])
    return first.module


def _cover_signal_score(nodes: list[object]) -> int:
    text = "".join(node.text for node in nodes)
    metadata_hits = sum(token in text for token in ("题目", "学院", "专业", "姓名", "指导教师", "完成日期"))
    has_graphic = any(node.elem.find(".//w:drawing", NS) is not None for node in nodes)
    return sum(("辽宁大学" in text, "毕业论文" in text or "毕业设计" in text, metadata_hits >= 2, has_graphic))


def plan_cover_replacement(document_root: ET.Element, document_model) -> CoverPlan:
    body = document_root.find("w:body", NS)
    if body is None:
        raise CoverReplacementError("document.xml 缺少正文容器")
    node_by_id = {id(node.elem): node for node in document_model.paragraphs}
    targets: list[ET.Element] = []
    cover_nodes: list[object] = []
    boundary = None
    for child in list(body):
        if child.tag == _q(W_NS, "sectPr"):
            continue
        nodes = _child_nodes(child, node_by_id)
        sections = {node.container_section for node in nodes}
        if boundary is None and sections == {"cover"}:
            targets.append(child)
            cover_nodes.extend(nodes)
            continue
        if "cover" in sections or len(sections) != 1:
            raise CoverReplacementError("封面边界不明确，已拒绝替换")
        boundary = child
        if _first_boundary_module(nodes) not in BOUNDARY_MODULES:
            raise CoverReplacementError("封面边界不明确，已拒绝替换")
        break
    if boundary is None or (targets and _cover_signal_score(cover_nodes) < 2):
        raise CoverReplacementError("封面边界不明确，已拒绝替换")
    return CoverPlan(body=body, targets=tuple(targets), boundary=boundary)


def _set_w_attr(element: ET.Element, name: str, value) -> None:
    element.set(_q(W_NS, name), str(value))


def _append_text_run(paragraph: ET.Element, text: str, *, size: int, font: str, bold: bool = False) -> None:
    run = ET.SubElement(paragraph, _q(W_NS, "r"))
    run_props = ET.SubElement(run, _q(W_NS, "rPr"))
    fonts = ET.SubElement(run_props, _q(W_NS, "rFonts"))
    for name in ("ascii", "hAnsi", "eastAsia", "cs"):
        _set_w_attr(fonts, name, font)
    _set_w_attr(fonts, "hint", "eastAsia")
    if bold:
        ET.SubElement(run_props, _q(W_NS, "b"))
        ET.SubElement(run_props, _q(W_NS, "bCs"))
    _set_w_attr(ET.SubElement(run_props, _q(W_NS, "sz")), "val", size)
    _set_w_attr(ET.SubElement(run_props, _q(W_NS, "szCs")), "val", size)
    text_elem = ET.SubElement(run, _q(W_NS, "t"))
    text_elem.text = text


def _paragraph(*, align: str = "center", before: int = 0, after: int = 0) -> ET.Element:
    paragraph = ET.Element(_q(W_NS, "p"))
    props = ET.SubElement(paragraph, _q(W_NS, "pPr"))
    _set_w_attr(ET.SubElement(props, _q(W_NS, "jc")), "val", align)
    spacing = ET.SubElement(props, _q(W_NS, "spacing"))
    _set_w_attr(spacing, "before", before)
    _set_w_attr(spacing, "after", after)
    return paragraph


def _drawing_run(rel_id: str, name: str, description: str, cx: int, cy: int, drawing_id: int) -> ET.Element:
    run = ET.Element(_q(W_NS, "r"))
    drawing = ET.SubElement(run, _q(W_NS, "drawing"))
    inline = ET.SubElement(drawing, _q(WP_NS, "inline"), {"distT": "0", "distB": "0", "distL": "0", "distR": "0"})
    ET.SubElement(inline, _q(WP_NS, "extent"), {"cx": str(cx), "cy": str(cy)})
    ET.SubElement(inline, _q(WP_NS, "effectExtent"), {"l": "0", "t": "0", "r": "0", "b": "0"})
    ET.SubElement(inline, _q(WP_NS, "docPr"), {"id": str(drawing_id), "name": name, "descr": description})
    ET.SubElement(inline, _q(WP_NS, "cNvGraphicFramePr"))
    _append_picture_graphic(inline, rel_id, name, cx, cy)
    return run


def _append_picture_graphic(inline: ET.Element, rel_id: str, name: str, cx: int, cy: int) -> None:
    graphic = ET.SubElement(inline, _q(A_NS, "graphic"))
    data = ET.SubElement(graphic, _q(A_NS, "graphicData"), {"uri": PIC_NS})
    picture = ET.SubElement(data, _q(PIC_NS, "pic"))
    non_visual = ET.SubElement(picture, _q(PIC_NS, "nvPicPr"))
    ET.SubElement(non_visual, _q(PIC_NS, "cNvPr"), {"id": "0", "name": name})
    ET.SubElement(non_visual, _q(PIC_NS, "cNvPicPr"))
    fill = ET.SubElement(picture, _q(PIC_NS, "blipFill"))
    ET.SubElement(fill, _q(A_NS, "blip"), {_q(R_NS, "embed"): rel_id})
    ET.SubElement(ET.SubElement(fill, _q(A_NS, "stretch")), _q(A_NS, "fillRect"))
    _append_picture_shape(picture, cx, cy)


def _append_picture_shape(picture: ET.Element, cx: int, cy: int) -> None:
    shape = ET.SubElement(picture, _q(PIC_NS, "spPr"))
    transform = ET.SubElement(shape, _q(A_NS, "xfrm"))
    ET.SubElement(transform, _q(A_NS, "off"), {"x": "0", "y": "0"})
    ET.SubElement(transform, _q(A_NS, "ext"), {"cx": str(cx), "cy": str(cy)})
    geometry = ET.SubElement(shape, _q(A_NS, "prstGeom"), {"prst": "rect"})
    ET.SubElement(geometry, _q(A_NS, "avLst"))


def _image_paragraph(rel_id: str, name: str, description: str, width: float, ratio: float, drawing_id: int) -> ET.Element:
    paragraph = _paragraph(before=100, after=180)
    cx = int(width * EMU_PER_INCH)
    paragraph.append(_drawing_run(rel_id, name, description, cx, int(cx / ratio), drawing_id))
    return paragraph


def _field_paragraph(text: str, *, label: bool) -> ET.Element:
    paragraph = _paragraph(align="left", before=70, after=70)
    props = paragraph.find("w:pPr", NS)
    if not label and props is not None:
        borders = ET.SubElement(props, _q(W_NS, "pBdr"))
        ET.SubElement(borders, _q(W_NS, "bottom"), {_q(W_NS, "val"): "single", _q(W_NS, "sz"): "6", _q(W_NS, "space"): "2", _q(W_NS, "color"): "000000"})
    _append_text_run(paragraph, text, size=28 if label else 30, font="Songti SC")
    return paragraph


def _field_cell(width: int, paragraph: ET.Element) -> ET.Element:
    cell = ET.Element(_q(W_NS, "tc"))
    props = ET.SubElement(cell, _q(W_NS, "tcPr"))
    _set_w_attr(ET.SubElement(props, _q(W_NS, "tcW")), "w", width)
    _set_w_attr(props.find("w:tcW", NS), "type", "dxa")
    _set_w_attr(ET.SubElement(props, _q(W_NS, "vAlign")), "val", "center")
    cell.append(paragraph)
    return cell


def _field_table(fields: dict[str, str]) -> ET.Element:
    table = ET.Element(_q(W_NS, "tbl"))
    props = ET.SubElement(table, _q(W_NS, "tblPr"))
    for tag, value in (("tblW", "7600"), ("tblLayout", "fixed"), ("jc", "center")):
        child = ET.SubElement(props, _q(W_NS, tag))
        _set_w_attr(child, "w" if tag == "tblW" else "type" if tag == "tblLayout" else "val", value)
    borders = ET.SubElement(props, _q(W_NS, "tblBorders"))
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        ET.SubElement(borders, _q(W_NS, edge), {_q(W_NS, "val"): "nil"})
    grid = ET.SubElement(table, _q(W_NS, "tblGrid"))
    for width in (2200, 5400):
        _set_w_attr(ET.SubElement(grid, _q(W_NS, "gridCol")), "w", width)
    for label, name in FIELD_LABELS:
        row = ET.SubElement(table, _q(W_NS, "tr"))
        row.append(_field_cell(2200, _field_paragraph(label, label=True)))
        row.append(_field_cell(5400, _field_paragraph(fields[name], label=False)))
    return table


def _section_break_paragraph() -> ET.Element:
    paragraph = _paragraph(after=0)
    props = paragraph.find("w:pPr", NS)
    section = ET.SubElement(props, _q(W_NS, "sectPr"))
    _set_w_attr(ET.SubElement(section, _q(W_NS, "type")), "val", "nextPage")
    page_size = ET.SubElement(section, _q(W_NS, "pgSz"))
    _set_w_attr(page_size, "w", "11906")
    _set_w_attr(page_size, "h", "16838")
    margins = ET.SubElement(section, _q(W_NS, "pgMar"))
    for name, value in (("top", 1417), ("right", 1417), ("bottom", 1417), ("left", 1417), ("header", 720), ("footer", 720), ("gutter", 283)):
        _set_w_attr(margins, name, value)
    _set_w_attr(ET.SubElement(section, _q(W_NS, "cols")), "space", 425)
    return paragraph


def _next_drawing_id(document_root: ET.Element) -> int:
    ids = [int(item.get("id")) for item in document_root.findall(".//wp:docPr", NS) if str(item.get("id", "")).isdigit()]
    return max(ids, default=0) + 1


def _cover_elements(fields: dict[str, str], rel_ids: dict[str, str], drawing_id: int) -> list[ET.Element]:
    wordmark = _image_paragraph(rel_ids["wordmark"], "LNU Cover Wordmark", "辽宁大学校名字样", 3.0, 300 / 92, drawing_id)
    anchor_run = ET.SubElement(wordmark, _q(W_NS, "r"))
    anchor_props = ET.SubElement(anchor_run, _q(W_NS, "rPr"))
    ET.SubElement(anchor_props, _q(W_NS, "vanish"))
    anchor_text = ET.SubElement(anchor_run, _q(W_NS, "t"))
    anchor_text.text = "辽宁大学"
    title = _paragraph(before=260, after=260)
    _append_text_run(title, "毕业论文（设计）", size=56, font="Heiti SC", bold=True)
    emblem = _image_paragraph(rel_ids["emblem"], "LNU Cover Emblem", "辽宁大学校徽", 1.55, 1.0, drawing_id + 1)
    return [wordmark, title, emblem, _field_table(fields), _section_break_paragraph()]


def _unique_target(rels_root: ET.Element, base_name: str) -> str:
    existing = {rel.get("Target") for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")}
    candidate = f"media/{base_name}"
    counter = 2
    while candidate in existing:
        stem, suffix = Path(base_name).stem, Path(base_name).suffix
        candidate = f"media/{stem}-{counter}{suffix}"
        counter += 1
    return candidate


def _unique_rel_id(rels_root: ET.Element, base: str) -> str:
    existing = {rel.get("Id") for rel in rels_root.findall(f"{{{PKG_REL_NS}}}Relationship")}
    candidate = base
    counter = 2
    while candidate in existing:
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


def _ensure_content_type(root: ET.Element, extension: str, content_type: str) -> None:
    defaults = root.findall(f"{{{CONTENT_TYPES_NS}}}Default")
    if any(item.get("Extension", "").lower() == extension for item in defaults):
        return
    default = ET.SubElement(root, _q(CONTENT_TYPES_NS, "Default"))
    default.set("Extension", extension)
    default.set("ContentType", content_type)


def _add_image_relation(rels_root: ET.Element, rel_id: str, target: str) -> None:
    relation = ET.SubElement(rels_root, _q(PKG_REL_NS, "Relationship"))
    relation.set("Id", rel_id)
    relation.set("Type", IMAGE_REL_TYPE)
    relation.set("Target", target)


def _install_assets(temp_dir: str, template_profile_id: str) -> tuple[dict[str, str], dict[str, bytes]]:
    if template_profile_id != "lnu":
        raise CoverReplacementError("固定官方封面目前仅支持辽宁大学 profile")
    root = Path(temp_dir)
    rels_path = root / "word/_rels/document.xml.rels"
    types_path = root / "[Content_Types].xml"
    rels_root = ET.parse(rels_path).getroot()
    types_root = ET.parse(types_path).getroot()
    asset_dir = Path(config_path("templates", "lnu", "cover-assets"))
    specs = (("wordmark", "wordmark.jpeg", "lnu-cover-wordmark.jpeg"), ("emblem", "emblem.png", "lnu-cover-emblem.png"))
    rel_ids: dict[str, str] = {}
    parts: dict[str, bytes] = {}
    for key, source_name, target_name in specs:
        target = _unique_target(rels_root, target_name)
        rel_id = _unique_rel_id(rels_root, f"rIdCover{key.title()}")
        _add_image_relation(rels_root, rel_id, target)
        payload = (asset_dir / source_name).read_bytes()
        parts[f"word/{target}"] = payload
        rel_ids[key] = rel_id
    _ensure_content_type(types_root, "png", "image/png")
    _ensure_content_type(types_root, "jpeg", "image/jpeg")
    parts["word/_rels/document.xml.rels"] = serialize_opc_root(rels_root, PKG_REL_NS)
    parts["[Content_Types].xml"] = serialize_opc_root(types_root, CONTENT_TYPES_NS)
    _write_package_parts(root, parts)
    return rel_ids, parts


def _write_package_parts(root: Path, parts: dict[str, bytes]) -> None:
    for name, payload in parts.items():
        target = root / name
        os.makedirs(target.parent, exist_ok=True)
        target.write_bytes(payload)


def _package_part(root: Path, updated_parts: Mapping[str, bytes], name: str) -> bytes:
    if name in updated_parts:
        return updated_parts[name]
    path = root / name
    if not path.is_file():
        raise CoverReplacementError(f"封面 OPC 部件缺失: {name}")
    return path.read_bytes()


def _parse_package_xml(root: Path, updated_parts: Mapping[str, bytes], name: str) -> ET.Element:
    try:
        return ET.fromstring(_package_part(root, updated_parts, name))
    except ET.ParseError as exc:
        raise CoverReplacementError(f"封面 OPC 部件无法解析: {name}") from exc


def _cover_prefix(document_root: ET.Element) -> tuple[list[ET.Element], ET.Element]:
    body = document_root.find("w:body", NS)
    if body is None:
        raise CoverReplacementError("封面分节缺少正文容器")
    children = list(body)
    for index, child in enumerate(children):
        section = child.find("w:pPr/w:sectPr", NS)
        if section is not None:
            return children[: index + 1], section
    raise CoverReplacementError("封面分节缺失")


def _validate_cover_section(elements: list[ET.Element], section: ET.Element) -> None:
    section_type = section.find("w:type", NS)
    page_size = section.find("w:pgSz", NS)
    valid_a4 = page_size is not None and page_size.get(_q(W_NS, "w")) == "11906" and page_size.get(_q(W_NS, "h")) == "16838"
    page_fields = [item for element in elements for item in element.findall(".//w:instrText", NS) if "PAGE" in (item.text or "").upper()]
    if section_type is None or section_type.get(_q(W_NS, "val")) != "nextPage" or not valid_a4:
        raise CoverReplacementError("封面分节必须是 A4 nextPage")
    if section.find("w:footerReference", NS) is not None or section.find("w:pgNumType", NS) is not None or page_fields:
        raise CoverReplacementError("封面分节不能包含页脚或页码")


def _validate_cover_fields(elements: list[ET.Element], fields: Mapping[str, str]) -> None:
    expected = {
        "".join(label.split()): fields[name]
        for label, name in FIELD_LABELS
    }
    actual: dict[str, str] = {}
    for element in elements:
        for row in element.findall(".//w:tr", NS):
            cells = row.findall("w:tc", NS)
            if len(cells) != 2:
                continue
            label = "".join("".join(cells[0].itertext()).split())
            if label not in expected:
                continue
            if label in actual:
                raise CoverReplacementError("固定封面六项字段不完整")
            actual[label] = "".join(cells[1].itertext()).strip()
    if actual != expected:
        raise CoverReplacementError("固定封面六项字段不完整")


def _cover_image_relations(document_root: ET.Element) -> dict[str, str]:
    relations: dict[str, str] = {}
    for inline in document_root.findall(".//wp:inline", NS):
        doc_props = inline.find("wp:docPr", NS)
        name = doc_props.get("name") if doc_props is not None else None
        if name not in COVER_DRAWING_ASSETS:
            continue
        blip = inline.find(".//a:blip", NS)
        rel_id = blip.get(_q(R_NS, "embed")) if blip is not None else None
        if not rel_id or name in relations:
            raise CoverReplacementError("固定封面图片关系不完整")
        relations[name] = rel_id
    if set(relations) != set(COVER_DRAWING_ASSETS):
        raise CoverReplacementError("固定封面图片关系不完整")
    return relations


def _resolve_image_targets(rels_root: ET.Element, rel_ids: Mapping[str, str]) -> dict[str, str]:
    by_id = {item.get("Id"): item for item in rels_root.findall(_q(PKG_REL_NS, "Relationship"))}
    targets: dict[str, str] = {}
    for name, rel_id in rel_ids.items():
        relation = by_id.get(rel_id)
        if relation is None or relation.get("Type") != IMAGE_REL_TYPE or relation.get("TargetMode"):
            raise CoverReplacementError("固定封面图片关系无法解析")
        target = posixpath.normpath(posixpath.join("word", relation.get("Target", "")))
        if not target.startswith("word/media/"):
            raise CoverReplacementError("固定封面图片关系目标无效")
        targets[name] = target
    return targets


def _validate_image_parts(root: Path, updated_parts: Mapping[str, bytes], targets: Mapping[str, str]) -> None:
    types_root = _parse_package_xml(root, updated_parts, "[Content_Types].xml")
    defaults = {
        item.get("Extension", "").lower(): item.get("ContentType")
        for item in types_root.findall(_q(CONTENT_TYPES_NS, "Default"))
    }
    asset_dir = Path(config_path("templates", "lnu", "cover-assets"))
    for drawing_name, target in targets.items():
        extension = Path(target).suffix.lstrip(".").lower()
        if defaults.get(extension) != IMAGE_CONTENT_TYPES.get(extension):
            raise CoverReplacementError("固定封面图片内容类型不完整")
        if _package_part(root, updated_parts, target) != (asset_dir / COVER_DRAWING_ASSETS[drawing_name]).read_bytes():
            raise CoverReplacementError("固定封面官方图片文件不完整")


def validate_cover_package(temp_dir: str, updated_parts: Mapping[str, bytes], cover_fields) -> None:
    fields = normalize_cover_fields(cover_fields)
    if fields is None:
        raise CoverReplacementError("固定封面六项字段不完整")
    root = Path(temp_dir)
    document_root = _parse_package_xml(root, updated_parts, "word/document.xml")
    cover_elements, section = _cover_prefix(document_root)
    _validate_cover_section(cover_elements, section)
    _validate_cover_fields(cover_elements, fields)
    rel_ids = _cover_image_relations(document_root)
    rels_root = _parse_package_xml(root, updated_parts, "word/_rels/document.xml.rels")
    targets = _resolve_image_targets(rels_root, rel_ids)
    _validate_image_parts(root, updated_parts, targets)


def replace_cover(document_root, document_model, temp_dir: str, template_profile_id: str, cover_fields) -> CoverReplacement:
    fields = normalize_cover_fields(cover_fields)
    if fields is None:
        raise ValueError("cover_fields 不能为空")
    plan = plan_cover_replacement(document_root, document_model)
    rel_ids, parts = _install_assets(temp_dir, template_profile_id)
    elements = _cover_elements(fields, rel_ids, _next_drawing_id(document_root))
    for target in plan.targets:
        plan.body.remove(target)
    insert_at = list(plan.body).index(plan.boundary)
    for offset, element in enumerate(elements):
        plan.body.insert(insert_at + offset, element)
    status = "replaced" if plan.targets else "inserted"
    return CoverReplacement(status, len(plan.targets), parts)
