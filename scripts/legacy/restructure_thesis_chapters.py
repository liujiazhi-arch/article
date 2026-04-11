import argparse
import os
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE_NS = "http://www.w3.org/XML/1998/namespace"
NSMAP = {"w": W_NS}

ET.register_namespace("w", W_NS)

TOC_STYLE_IDS = {"13", "16", "19", "TOC1", "TOC2", "TOC3"}
TOC_TITLE_STYLE_IDS = {"60", "TOCHeading"}
HEADING_STYLE_IDS = {
    "2",
    "4",
    "5",
    "6",
    "Heading1",
    "Heading2",
    "Heading3",
    "Heading4",
}
DOUBLE_NUMBER_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+){1,3})\s+(\d+(?:\.\d+){1,3})\s+(.+?)\s*$"
)
TOC_PAGE_HINTS = {
    "序 言": "1",
    "0.1 研究背景": "1",
    "0.1.1 明胶概述": "1",
    "0.1.2 明胶改性技术概述": "2",
    "0.1.3 明胶制备方法": "4",
    "0.2 研究目的和意义": "5",
    "第1章  实验材料与方法": "7",
    "1.1 试验方法": "7",
    "1.1.1 改性明胶的制备": "7",
    "1.1.2 溶胀率测定": "7",
    "1.1.3 水中溶失率测定": "8",
    "1.1.4 正式实验分组及改性鹿皮样品制备": "8",
    "1.1.5 持水率测定": "9",
    "1.1.6 持油率测定": "10",
    "1.1.7 乳化活性及乳化稳定性测定": "10",
    "1.1.8 紫外吸收光谱测定": "10",
    "1.1.9 傅里叶变换红外光谱测定": "11",
    "1.2 数据处理与统计分析": "11",
    "第2章  实验结果与分析": "12",
    "2.1 不同改性技术鹿皮明胶改性条件的筛选": "12",
    "2.1.1 溶胀特性分析": "12",
    "2.1.2 溶失特性分析": "13",
    "2.2 不同改性技术对鹿皮明胶功能特性的影响": "13",
    "2.2.1 凝胶强度分析": "13",
    "2.2.2 乳化活性": "15",
    "2.2.3 乳化稳定性分析": "15",
    "2.2.4 持水性分析": "16",
    "2.2.5 持油性分析": "17",
    "2.3 不同改性技术对鹿皮明胶结构特性的影响": "17",
    "2.3.1 紫外吸收光谱分析": "17",
    "2.3.2 傅里叶变换红外光谱分析": "18",
    "第3章  结论与展望": "19",
    "3.1 结论": "19",
    "3.2 展望": "22",
}
TOC_STYLE_SPECS = {
    "16": {"east_asia": "黑体", "size": "28", "after": "100", "line": "276", "line_rule": "auto", "left": None},
    "19": {"east_asia": "宋体", "size": "24", "after": "100", "line": "276", "line_rule": "auto", "left": "420"},
    "13": {"east_asia": "宋体", "size": "24", "after": "100", "line": "276", "line_rule": "auto", "left": "840"},
}
TOC_TITLE_SPEC = {"east_asia": "黑体", "size": "32", "after": "0", "line": "240", "line_rule": "auto"}


def paragraph_text(p_elem: ET.Element) -> str:
    return "".join(t.text or "" for t in p_elem.findall(".//w:t", NSMAP)).strip()


def paragraph_style_id(p_elem: ET.Element) -> str:
    p_style = p_elem.find("w:pPr/w:pStyle", NSMAP)
    if p_style is None:
        return ""
    return p_style.get(f"{{{W_NS}}}val", "")


def rewrite_paragraph_text(p_elem: ET.Element, new_text: str) -> bool:
    text_elems = p_elem.findall(".//w:t", NSMAP)
    if not text_elems:
        return False
    text_elems[0].text = new_text
    text_elems[0].set(f"{{{XML_SPACE_NS}}}space", "preserve")
    for text_elem in text_elems[1:]:
        text_elem.text = ""
    return True


def get_run_text(run_elem: ET.Element) -> str:
    return "".join(t.text or "" for t in run_elem.findall(".//w:t", NSMAP))


def first_text_node(run_elem: ET.Element) -> ET.Element | None:
    return run_elem.find("w:t", NSMAP)


def make_text_run_like(run_elem: ET.Element, text: str) -> ET.Element:
    new_run = ET.Element(f"{{{W_NS}}}r")
    r_pr = run_elem.find("w:rPr", NSMAP)
    if r_pr is not None:
        new_run.append(ET.fromstring(ET.tostring(r_pr, encoding="unicode")))
    text_elem = ET.SubElement(new_run, f"{{{W_NS}}}t")
    text_elem.text = text
    if text.startswith(" ") or text.endswith(" "):
        text_elem.set(f"{{{XML_SPACE_NS}}}space", "preserve")
    return new_run


def ensure_child(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag, NSMAP)
    if child is None:
        child = ET.SubElement(parent, f"{{{W_NS}}}{tag.split(':', 1)[1]}")
    return child


def set_run_fonts(r_pr: ET.Element, east_asia: str, size: str) -> None:
    r_fonts = ensure_child(r_pr, "w:rFonts")
    r_fonts.set(f"{{{W_NS}}}ascii", "Times New Roman")
    r_fonts.set(f"{{{W_NS}}}hAnsi", "Times New Roman")
    r_fonts.set(f"{{{W_NS}}}cs", "Times New Roman")
    r_fonts.set(f"{{{W_NS}}}eastAsia", east_asia)

    sz = ensure_child(r_pr, "w:sz")
    sz.set(f"{{{W_NS}}}val", size)
    sz_cs = ensure_child(r_pr, "w:szCs")
    sz_cs.set(f"{{{W_NS}}}val", size)


def normalize_toc_paragraph_runs(p_elem: ET.Element) -> None:
    style_id = paragraph_style_id(p_elem)
    if style_id in TOC_TITLE_STYLE_IDS:
        spec = TOC_TITLE_SPEC
    else:
        spec = TOC_STYLE_SPECS.get(style_id)
    if spec is None:
        return

    for run_elem in p_elem.findall("w:r", NSMAP):
        r_pr = ensure_child(run_elem, "w:rPr")
        set_run_fonts(r_pr, spec["east_asia"], spec["size"])


def normalize_toc_title_paragraph(p_elem: ET.Element) -> None:
    if paragraph_style_id(p_elem) not in TOC_TITLE_STYLE_IDS:
        return
    p_pr = ensure_child(p_elem, "w:pPr")
    p_style = ensure_child(p_pr, "w:pStyle")
    p_style.set(f"{{{W_NS}}}val", "60")
    jc = ensure_child(p_pr, "w:jc")
    jc.set(f"{{{W_NS}}}val", "center")
    spacing = ensure_child(p_pr, "w:spacing")
    spacing.set(f"{{{W_NS}}}before", "0")
    spacing.set(f"{{{W_NS}}}after", "0")
    spacing.set(f"{{{W_NS}}}line", TOC_TITLE_SPEC["line"])
    spacing.set(f"{{{W_NS}}}lineRule", TOC_TITLE_SPEC["line_rule"])
    normalize_toc_paragraph_runs(p_elem)


def normalize_toc_entry_paragraph(p_elem: ET.Element) -> None:
    style_id = paragraph_style_id(p_elem)
    spec = TOC_STYLE_SPECS.get(style_id)
    if spec is None:
        return

    p_pr = ensure_child(p_elem, "w:pPr")
    spacing = ensure_child(p_pr, "w:spacing")
    spacing.set(f"{{{W_NS}}}before", "0")
    spacing.set(f"{{{W_NS}}}after", spec["after"])
    spacing.set(f"{{{W_NS}}}line", spec["line"])
    spacing.set(f"{{{W_NS}}}lineRule", spec["line_rule"])

    for child in list(p_pr):
        if child.tag == f"{{{W_NS}}}ind":
            p_pr.remove(child)
    if spec["left"] is not None:
        ind = ET.SubElement(p_pr, f"{{{W_NS}}}ind")
        ind.set(f"{{{W_NS}}}left", spec["left"])
        ind.set(f"{{{W_NS}}}firstLine", "0")

    tabs = p_pr.find("w:tabs", NSMAP)
    if tabs is None:
        tabs = ET.SubElement(p_pr, f"{{{W_NS}}}tabs")
    for child in list(tabs):
        tabs.remove(child)
    tab = ET.SubElement(tabs, f"{{{W_NS}}}tab")
    tab.set(f"{{{W_NS}}}val", "right")
    tab.set(f"{{{W_NS}}}leader", "dot")
    tab.set(f"{{{W_NS}}}pos", "8820")

    normalize_toc_paragraph_runs(p_elem)


def normalize_toc_styles(styles_root: ET.Element) -> None:
    for style_id, spec in TOC_STYLE_SPECS.items():
        style_elem = styles_root.find(f"w:style[@w:styleId='{style_id}']", NSMAP)
        if style_elem is None:
            continue
        p_pr = ensure_child(style_elem, "w:pPr")
        spacing = ensure_child(p_pr, "w:spacing")
        spacing.set(f"{{{W_NS}}}before", "0")
        spacing.set(f"{{{W_NS}}}after", spec["after"])
        spacing.set(f"{{{W_NS}}}line", spec["line"])
        spacing.set(f"{{{W_NS}}}lineRule", spec["line_rule"])
        for child in list(p_pr):
            if child.tag == f"{{{W_NS}}}ind":
                p_pr.remove(child)
        if spec["left"] is not None:
            ind = ET.SubElement(p_pr, f"{{{W_NS}}}ind")
            ind.set(f"{{{W_NS}}}left", spec["left"])
            ind.set(f"{{{W_NS}}}firstLine", "0")
        else:
            ind = ET.SubElement(p_pr, f"{{{W_NS}}}ind")
            ind.set(f"{{{W_NS}}}firstLine", "0")
        r_pr = ensure_child(style_elem, "w:rPr")
        set_run_fonts(r_pr, spec["east_asia"], spec["size"])

    title_style = styles_root.find("w:style[@w:styleId='60']", NSMAP)
    if title_style is not None:
        p_pr = ensure_child(title_style, "w:pPr")
        spacing = ensure_child(p_pr, "w:spacing")
        spacing.set(f"{{{W_NS}}}before", "0")
        spacing.set(f"{{{W_NS}}}after", TOC_TITLE_SPEC["after"])
        spacing.set(f"{{{W_NS}}}line", TOC_TITLE_SPEC["line"])
        spacing.set(f"{{{W_NS}}}lineRule", TOC_TITLE_SPEC["line_rule"])
        jc = ensure_child(p_pr, "w:jc")
        jc.set(f"{{{W_NS}}}val", "center")
        r_pr = ensure_child(title_style, "w:rPr")
        set_run_fonts(r_pr, TOC_TITLE_SPEC["east_asia"], TOC_TITLE_SPEC["size"])


def clean_toc_entry_visible_text(p_elem: ET.Element) -> bool:
    style_id = paragraph_style_id(p_elem)
    if style_id not in TOC_STYLE_IDS:
        return False

    runs = [child for child in list(p_elem) if child.tag == f"{{{W_NS}}}r"]
    if not runs:
        return False

    seen_outer_sep = False
    after_tab = False
    in_pageref_instr = False
    after_pageref_sep = False
    visible_runs: list[ET.Element] = []
    page_result_runs: list[ET.Element] = []
    page_result_anchor: ET.Element | None = None
    for run_elem in runs:
        fld_char = run_elem.find("w:fldChar", NSMAP)
        instr_text = run_elem.find("w:instrText", NSMAP)

        if not seen_outer_sep:
            if fld_char is not None and fld_char.get(f"{{{W_NS}}}fldCharType", "") == "separate":
                seen_outer_sep = True
            continue

        if not after_tab:
            if run_elem.find("w:tab", NSMAP) is not None:
                after_tab = True
                continue
            if instr_text is not None or fld_char is not None:
                continue
            if run_elem.findall(".//w:t", NSMAP):
                visible_runs.append(run_elem)
            continue

        if instr_text is not None:
            if "PAGEREF" in (instr_text.text or "").upper():
                in_pageref_instr = True
            continue

        if fld_char is not None:
            fld_type = fld_char.get(f"{{{W_NS}}}fldCharType", "")
            if fld_type == "separate" and in_pageref_instr:
                after_pageref_sep = True
                in_pageref_instr = False
                page_result_anchor = run_elem
                continue
            if fld_type == "end" and after_pageref_sep:
                break
            continue

        if after_pageref_sep and run_elem.findall(".//w:t", NSMAP):
            page_result_runs.append(run_elem)

    if not visible_runs:
        return False

    visible_text = "".join(get_run_text(run_elem) for run_elem in visible_runs).strip()
    trailing_page_match = re.search(r"(\d+)\s*$", visible_text)
    trailing_page = trailing_page_match.group(1) if trailing_page_match else ""
    cleaned_text = re.sub(r"\s*\d+\s*$", "", visible_text).strip()
    if not cleaned_text:
        cleaned_text = visible_text
    page_hint = trailing_page or TOC_PAGE_HINTS.get(cleaned_text, "")

    first_text = None
    for run_elem in visible_runs:
        first_text = first_text_node(run_elem)
        if first_text is not None:
            break
    changed = False
    if first_text is not None and cleaned_text != visible_text:
        first_text.text = cleaned_text
        first_text.set(f"{{{XML_SPACE_NS}}}space", "preserve")
        first_seen = False
        for run_elem in visible_runs:
            for text_elem in run_elem.findall(".//w:t", NSMAP):
                if not first_seen:
                    first_seen = True
                    continue
                text_elem.text = ""
        changed = True

    if page_hint:
        if page_result_runs:
            page_text = "".join(get_run_text(run_elem) for run_elem in page_result_runs).strip()
            if page_text != page_hint:
                first_page_text = None
                for run_elem in page_result_runs:
                    first_page_text = first_text_node(run_elem)
                    if first_page_text is not None:
                        break
                if first_page_text is not None:
                    first_page_text.text = page_hint
                    first_seen = False
                    for run_elem in page_result_runs:
                        for text_elem in run_elem.findall(".//w:t", NSMAP):
                            if not first_seen:
                                first_seen = True
                                continue
                            text_elem.text = ""
                    changed = True
        elif page_result_anchor is not None:
            children = list(p_elem)
            insert_index = children.index(page_result_anchor) + 1
            template_run = visible_runs[0]
            p_elem.insert(insert_index, make_text_run_like(template_run, page_hint))
            changed = True

    return changed


def clean_duplicate_heading_numbers(p_elem: ET.Element) -> bool:
    style_id = paragraph_style_id(p_elem)
    if style_id not in HEADING_STYLE_IDS:
        return False

    text = paragraph_text(p_elem)
    match = DOUBLE_NUMBER_PATTERN.match(text)
    if not match:
        return False

    _, current_number, title = match.groups()
    return rewrite_paragraph_text(p_elem, f"{current_number} {title}")


def ensure_update_fields(settings_xml: bytes | None) -> bytes:
    if settings_xml:
        root = ET.fromstring(settings_xml)
    else:
        root = ET.Element(f"{{{W_NS}}}settings")

    update_fields = root.find("w:updateFields", NSMAP)
    if update_fields is None:
        update_fields = ET.SubElement(root, f"{{{W_NS}}}updateFields")
    update_fields.set(f"{{{W_NS}}}val", "true")

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(args.input) as zin:
            zin.extractall(tmpdir)

        document_xml = os.path.join(tmpdir, "word", "document.xml")
        settings_xml = os.path.join(tmpdir, "word", "settings.xml")
        styles_xml = os.path.join(tmpdir, "word", "styles.xml")

        tree = ET.parse(document_xml)
        root = tree.getroot()
        body = root.find("w:body", NSMAP)
        if body is None:
            raise RuntimeError("document.xml missing w:body")

        styles_tree = ET.parse(styles_xml)
        styles_root = styles_tree.getroot()
        normalize_toc_styles(styles_root)

        changed = False
        for p_elem in body.findall("w:p", NSMAP):
            normalize_toc_title_paragraph(p_elem)
            normalize_toc_entry_paragraph(p_elem)
            if clean_toc_entry_visible_text(p_elem):
                changed = True
            if clean_duplicate_heading_numbers(p_elem):
                changed = True

        tree.write(document_xml, encoding="UTF-8", xml_declaration=True)
        styles_tree.write(styles_xml, encoding="UTF-8", xml_declaration=True)

        existing_settings = None
        if os.path.exists(settings_xml):
            with open(settings_xml, "rb") as handle:
                existing_settings = handle.read()
        with open(settings_xml, "wb") as handle:
            handle.write(ensure_update_fields(existing_settings))

        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as zout:
            for folder, _, files in os.walk(tmpdir):
                for file_name in files:
                    full_path = os.path.join(folder, file_name)
                    arcname = os.path.relpath(full_path, tmpdir)
                    zout.write(full_path, arcname)

        if not changed:
            print("No TOC text or duplicate heading numbers needed repair.")


if __name__ == "__main__":
    main()
